"""Dramatiq actor that drives a workflow against every dataset case.

Flow:
    1. Load EvalRun + Dataset cases (oldest-first by order_index)
    2. Flip EvalRun to ``running`` + snapshot case count
    3. For each case:
        a. Create a synthetic Run tagged
           ``triggered_by_kind=eval``, ``triggered_by_id=eval_run.id``
        b. Drive the engine inline via ``walk_run``
        c. Compare the Run's output_data to the case's
           expected_output via the assertion strategy
        d. Insert an EvalRunCase row with the result
        e. Increment the EvalRun's pass/fail/error counters
    4. Flip EvalRun to ``succeeded`` (status reflects the actor's
       lifecycle, not the workflow's pass rate — operators read
       the counters for that)

Session discipline:
    All writes through ``session.flush()``. The actor framework
    commits at task completion. Each case's synthetic Run lands
    in the same transaction as the EvalRunCase that points at
    it; a mid-actor crash rolls back the partial work cleanly.

Failure isolation:
    A per-case failure (engine error, comparator raise) is
    captured into ``EvalRunCase.error_message`` and the actor
    continues. Only an actor-level exception (DB outage,
    misconfigured eval) flips the EvalRun to ``failed``. This
    matches the workflow author's intent: "show me everything
    that ran, including the cases that errored", not "abort the
    whole eval on the first hiccup".
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select

from rapidly.agents.execution.engine import walk_run
from rapidly.core.utils import now_utc
from rapidly.models import (
    AssertionStrategy,
    DatasetCase,
    EvalRun,
    EvalRunCase,
    EvalRunStatus,
    Run,
    RunStatus,
    TriggeredByKind,
)
from rapidly.worker import AsyncSessionMaker, TaskPriority, actor

_log = structlog.get_logger(__name__)


@actor(actor_name="agents.eval.run", priority=TaskPriority.LOW, max_retries=2)
async def run_eval(eval_run_id: UUID) -> None:
    """Execute the eval run identified by ``eval_run_id``."""
    async with AsyncSessionMaker() as session:
        try:
            await _run_eval_inner(session, eval_run_id)
        except Exception:
            _log.exception("agents.eval.run.unhandled", eval_run_id=str(eval_run_id))
            raise


async def _run_eval_inner(session: Any, eval_run_id: UUID) -> None:
    eval_run = await _load_eval_run(session, eval_run_id)
    if eval_run is None:
        _log.warning("agents.eval.run.missing", eval_run_id=str(eval_run_id))
        return
    if eval_run.status in (
        EvalRunStatus.succeeded,
        EvalRunStatus.failed,
        EvalRunStatus.cancelled,
    ):
        _log.info(
            "agents.eval.run.terminal_skip",
            eval_run_id=str(eval_run_id),
            status=eval_run.status,
        )
        return

    # Load cases in display order so per-case results match what
    # the operator sees in the dataset editor.
    cases = (
        (
            await session.execute(
                select(DatasetCase)
                .where(DatasetCase.dataset_id == eval_run.dataset_id)
                .order_by(DatasetCase.order_index.asc(), DatasetCase.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    eval_run.status = EvalRunStatus.running
    eval_run.started_at = now_utc()
    eval_run.case_count = len(cases)
    await session.flush()

    for case in cases:
        await _execute_case(session, eval_run=eval_run, case=case)

    eval_run.status = EvalRunStatus.succeeded
    eval_run.completed_at = now_utc()
    await session.flush()


async def _execute_case(
    session: Any,
    *,
    eval_run: EvalRun,
    case: DatasetCase,
) -> None:
    """Run one case through the engine + record the result."""
    started = time.monotonic()
    eval_case = EvalRunCase(
        eval_run_id=eval_run.id,
        case_id=case.id,
        case_name=case.name,
        case_input_data=dict(case.input_data),
        case_expected_output=(
            dict(case.expected_output) if case.expected_output is not None else None
        ),
    )

    try:
        synthetic_run = Run(
            workflow_version_id=eval_run.workflow_version_id,
            triggered_by_kind=TriggeredByKind.eval,
            triggered_by_id=eval_run.id,
            status=RunStatus.pending,
            input_data=dict(case.input_data),
        )
        session.add(synthetic_run)
        await session.flush()

        await walk_run(session, synthetic_run.id)
        # Re-read the run to pick up its final status — walk_run
        # mutates it in place but we want explicit confirmation.
        await session.refresh(synthetic_run)

        eval_case.run_id = synthetic_run.id

        if synthetic_run.status != RunStatus.succeeded:
            # Engine-side failure. Capture the message and mark
            # the case as errored — distinct from "wrong answer".
            eval_case.error_message = (
                synthetic_run.error_message or f"run status: {synthetic_run.status}"
            )[:1000]
            eval_run.error_count += 1
        elif case.expected_output is None:
            # Qualitative case — record actual_output but don't
            # score. The pass/fail counters don't move.
            eval_case.actual_output = dict(synthetic_run.output_data or {})
            # passed stays None.
        else:
            eval_case.actual_output = dict(synthetic_run.output_data or {})
            passed = _compare(
                strategy=eval_run.assertion_strategy,
                actual=eval_case.actual_output,
                expected=case.expected_output,
            )
            eval_case.passed = passed
            if passed:
                eval_run.pass_count += 1
            else:
                eval_run.fail_count += 1

    except Exception as exc:
        # Actor-side failure (DB hiccup, comparator bug). Record
        # against the case + bump the error counter so the
        # operator sees what happened without the whole eval
        # aborting.
        eval_case.error_message = str(exc)[:1000]
        eval_run.error_count += 1
        _log.exception(
            "agents.eval.case.failed",
            eval_run_id=str(eval_run.id),
            case_id=str(case.id),
        )

    eval_case.duration_ms = int((time.monotonic() - started) * 1000)
    session.add(eval_case)
    await session.flush()


def _compare(
    *,
    strategy: AssertionStrategy,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    """Score actual_output against expected_output.

    Strategies (M4.8b + M4.8c):
        - ``exact_match``  — Python ``==``. Brittle for non-
          deterministic LLM output; precise for structured
          extraction workflows.
        - ``json_schema``  — ``expected`` is treated as a JSON
          Schema, ``actual`` validated against it. Loose enough
          to accept "any field-shape match" while still pinning
          required keys + types. The case author writes a schema
          per case (or shares one across cases via a JSON pointer
          in the case input — future v2).

    ``llm_judge`` lands in M4.8d.
    """
    if strategy == AssertionStrategy.exact_match:
        return actual == expected
    if strategy == AssertionStrategy.json_schema:
        # Inline import — jsonschema is only needed when this
        # strategy is configured. Keeps the actor's import-time
        # surface lean for the common exact_match path.
        from jsonschema import ValidationError, validate

        try:
            validate(instance=actual, schema=expected)
        except ValidationError:
            return False
        return True
    raise ValueError(f"unsupported assertion_strategy {strategy!r}")


async def _load_eval_run(session: Any, eval_run_id: UUID) -> EvalRun | None:
    stmt = select(EvalRun).where(EvalRun.id == eval_run_id)
    return (await session.execute(stmt)).scalar_one_or_none()
