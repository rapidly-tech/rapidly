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
from rapidly.agents.execution.handlers.llm import structured_output_handler
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
            passed = await _compare(
                session=session,
                eval_run=eval_run,
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


async def _compare(
    *,
    session: Any,
    eval_run: EvalRun,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    """Score actual_output against expected_output.

    Strategies (M4.8b–d):
        - ``exact_match``  — Python ``==``. Brittle for non-
          deterministic LLM output; precise for structured
          extraction workflows.
        - ``json_schema``  — ``expected`` is treated as a JSON
          Schema, ``actual`` validated against it. Loose enough
          to accept "any field-shape match" while still pinning
          required keys + types.
        - ``llm_judge``    — a grader LLM scores ``actual``
          against ``expected`` (interpreted as a free-form
          rubric) and returns ``passed`` + ``reason``. Costs
          tokens per case. Uses the workspace's configured
          credentials via the existing resolver.
    """
    strategy = eval_run.assertion_strategy
    if strategy == AssertionStrategy.exact_match:
        return actual == expected
    if strategy == AssertionStrategy.json_schema:
        from jsonschema import ValidationError, validate

        try:
            validate(instance=actual, schema=expected)
        except ValidationError:
            return False
        return True
    if strategy == AssertionStrategy.llm_judge:
        return await _llm_judge(
            session=session,
            eval_run=eval_run,
            actual=actual,
            expected=expected,
        )
    raise ValueError(f"unsupported assertion_strategy {strategy!r}")


async def _llm_judge(
    *,
    session: Any,
    eval_run: EvalRun,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    """Use a grader LLM to score actual vs expected.

    The judge sees the case's ``expected_output`` as a rubric
    (free-form criteria, JSON-serialised) and the workflow's
    ``actual_output`` as the candidate to grade. It's prompted
    to return a typed pass/fail with a one-sentence reason.
    The reason isn't persisted today — operators reading the
    eval-case row just see the pass/fail — but the grader sees
    the prompt to reason about it, which improves the binary
    decision's quality. The reason text will land in
    ``EvalRunCase.judge_reason`` in M4.8e.

    Credential resolution + usage attribution all run through
    the same machinery the LLM handler uses, so judge calls
    show up in the workspace's LlmUsage rollups exactly like
    workflow LLM calls do.
    """
    judge_model_id = eval_run.judge_model_id
    if not judge_model_id:
        raise ValueError(
            "llm_judge requires eval_run.judge_model_id; "
            "EvalRunTrigger should have caught this at submit time."
        )

    # Build a synthetic ctx so the LLM handler's _resolve_credential
    # can look up the workspace's grader credential exactly like a
    # workflow-LLM-node call would. The handler reads:
    #   - ctx["session"] for the credential lookup
    #   - ctx["workspace_id"] for tenancy scope
    #   - ctx["run_id"] / ctx["node_run_id"] for usage attribution
    # (run_id stays None — the judge call isn't tied to a single
    # synthetic Run; the LlmUsage row carries workspace_id which
    # is enough for billing rollups.)
    ctx = {
        "session": session,
        "workspace_id": eval_run.workspace_id,
        "run_id": None,
        "node_run_id": None,
    }

    if ":" not in judge_model_id:
        raise ValueError(f"judge_model_id {judge_model_id!r} must be 'provider:model'")
    provider, model = judge_model_id.split(":", 1)

    node_config = {
        "provider": provider,
        "model": model,
        "system_prompt": _JUDGE_SYSTEM_PROMPT,
        "prompt_template": _JUDGE_PROMPT_TEMPLATE,
        "schema_json": {
            "type": "object",
            "required": ["passed"],
            "properties": {
                "passed": {"type": "boolean"},
                "reason": {"type": "string"},
            },
        },
    }
    input_data = {
        "expected": _safe_dump(expected),
        "actual": _safe_dump(actual),
    }

    out = await structured_output_handler(ctx, node_config, input_data)
    data = out.get("data") or {}
    return bool(data.get("passed", False))


def _safe_dump(obj: Any) -> str:
    """JSON-serialise ``obj`` for safe inclusion in the judge
    prompt. Falls back to ``repr`` on non-serialisable types so
    the judge sees something rather than the case erroring.
    """
    import json

    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return repr(obj)


_JUDGE_SYSTEM_PROMPT = """\
You are an evaluator grading workflow outputs against a rubric.

You'll see two JSON documents:
- EXPECTED: the rubric/criteria the actual output should satisfy.
  This is NOT a literal answer to match — interpret it as a
  description of what a passing answer looks like.
- ACTUAL: the workflow's output that needs grading.

Return a structured judgement:
- passed: true if ACTUAL satisfies the rubric, false otherwise
- reason: one-sentence explanation (under 200 chars)

Be strict about clear failures (missing required behaviour,
wrong direction). Be lenient about paraphrasing — if ACTUAL
says the same thing as EXPECTED in different words, that's
a pass.
"""

_JUDGE_PROMPT_TEMPLATE = """\
EXPECTED:
{expected}

ACTUAL:
{actual}

Grade the ACTUAL against the EXPECTED rubric.
"""


async def _load_eval_run(session: Any, eval_run_id: UUID) -> EvalRun | None:
    stmt = select(EvalRun).where(EvalRun.id == eval_run_id)
    return (await session.execute(stmt)).scalar_one_or_none()
