"""End-to-end test for the M4.8b eval runner actor.

Builds a minimal workflow (single echo node), seeds a dataset
with three cases (one matching, one mismatching, one with no
expected_output for qualitative review), triggers the runner,
and asserts the counters + per-case results.

Doesn't make any LLM calls — uses the echo handler so the
test is fully deterministic.
"""

from __future__ import annotations

import uuid

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import select

from rapidly.agents.eval_run import workers as eval_workers
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    Dataset,
    DatasetCase,
    EvalRun,
    EvalRunCase,
    EvalRunStatus,
    User,
    Workflow,
    WorkflowVersion,
    Workspace,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncSession


async def _member_principal(
    session: AsyncSession, workspace: Workspace
) -> AuthPrincipal[User]:
    user = User(email=f"u-{uuid.uuid4().hex[:6]}@example.com")
    session.add(user)
    await session.flush()
    session.add(WorkspaceMembership(user_id=user.id, workspace_id=workspace.id))
    await session.flush()
    return AuthPrincipal(subject=user, scopes=set(), session=None)


async def _seed_workflow_version(
    session: AsyncSession,
    workspace: Workspace,
) -> WorkflowVersion:
    """Build a single-echo-node workflow + version.

    The echo handler copies its input straight through to its
    output, so the workflow's output_data is exactly the case's
    input_data. We compare against that in the cases below.
    """
    # WorkflowVersion requires created_by_id (a User). Create
    # one inline so the seed is self-contained.
    creator = User(email=f"creator-{uuid.uuid4().hex[:6]}@example.com")
    session.add(creator)
    await session.flush()

    workflow = Workflow(workspace_id=workspace.id, name="echo-only")
    session.add(workflow)
    await session.flush()

    version = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=1,
        graph_json={
            "nodes": [{"id": "n1", "type": "echo", "config": {}}],
            "edges": [],
        },
        created_by_id=creator.id,
    )
    session.add(version)
    await session.flush()
    return version


@pytest.mark.asyncio
class TestEvalRunner:
    async def test_runs_dataset_and_records_results(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        principal = await _member_principal(session, workspace)
        version = await _seed_workflow_version(session, workspace)

        # Dataset with three cases:
        #   1. expected matches what echo produces  → pass
        #   2. expected differs                     → fail
        #   3. no expected_output                   → qualitative
        dataset = Dataset(workspace_id=workspace.id, name="echo-eval")
        session.add(dataset)
        await session.flush()
        cases = [
            DatasetCase(
                dataset_id=dataset.id,
                name="case-pass",
                input_data={"x": 1},
                expected_output={"x": 1},
                order_index=0,
            ),
            DatasetCase(
                dataset_id=dataset.id,
                name="case-fail",
                input_data={"x": 2},
                expected_output={"x": 99},
                order_index=1,
            ),
            DatasetCase(
                dataset_id=dataset.id,
                name="case-qualitative",
                input_data={"x": 3},
                expected_output=None,
                order_index=2,
            ),
        ]
        for c in cases:
            session.add(c)
        await session.flush()

        eval_run = EvalRun(
            workspace_id=workspace.id,
            dataset_id=dataset.id,
            workflow_version_id=version.id,
        )
        session.add(eval_run)
        await session.flush()

        # Route the actor's AsyncSessionMaker to the test session
        # so writes land in the same transaction. The actor uses
        # this context-manager idiom; the test fakes it with a
        # plain ctx that yields the existing session.
        class _Ctx:
            async def __aenter__(self) -> AsyncSession:
                return session

            async def __aexit__(self, *args: object) -> None:
                return None

        mocker.patch.object(eval_workers, "AsyncSessionMaker", return_value=_Ctx())

        await eval_workers.run_eval(eval_run.id)
        await session.refresh(eval_run)

        # Top-level eval state
        assert eval_run.status == EvalRunStatus.succeeded
        assert eval_run.case_count == 3
        assert eval_run.pass_count == 1
        assert eval_run.fail_count == 1
        # Qualitative case doesn't increment pass/fail; it also
        # doesn't increment error_count (no failure happened).
        assert eval_run.error_count == 0
        assert eval_run.started_at is not None
        assert eval_run.completed_at is not None

        # Per-case rows
        rows = (
            (
                await session.execute(
                    select(EvalRunCase)
                    .where(EvalRunCase.eval_run_id == eval_run.id)
                    .order_by(EvalRunCase.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 3

        by_name = {r.case_name: r for r in rows}
        assert by_name["case-pass"].passed is True
        assert by_name["case-fail"].passed is False
        # Qualitative — passed stays None (not asserted), but
        # actual_output is still captured for review.
        assert by_name["case-qualitative"].passed is None
        assert by_name["case-qualitative"].actual_output == {"x": 3}

        # Every case has a run_id — operators can drill into the
        # synthetic Run to see per-NodeRun timing.
        assert all(r.run_id is not None for r in rows)
        # And every case has a duration recorded (echo is fast
        # but non-zero milliseconds).
        assert all(r.duration_ms is not None and r.duration_ms >= 0 for r in rows)

        # Use principal to avoid unused-var warning (no auth path
        # exercised inside the actor itself — the API-layer
        # actions.trigger does that check).
        assert principal is not None

    async def test_empty_dataset_completes_with_zero_counts(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        # An eval against an empty dataset is valid; runner should
        # transition pending → running → succeeded with all
        # counters at zero.
        version = await _seed_workflow_version(session, workspace)
        dataset = Dataset(workspace_id=workspace.id, name="empty")
        session.add(dataset)
        await session.flush()

        eval_run = EvalRun(
            workspace_id=workspace.id,
            dataset_id=dataset.id,
            workflow_version_id=version.id,
        )
        session.add(eval_run)
        await session.flush()

        class _Ctx:
            async def __aenter__(self) -> AsyncSession:
                return session

            async def __aexit__(self, *args: object) -> None:
                return None

        mocker.patch.object(eval_workers, "AsyncSessionMaker", return_value=_Ctx())

        await eval_workers.run_eval(eval_run.id)
        await session.refresh(eval_run)

        assert eval_run.status == EvalRunStatus.succeeded
        assert eval_run.case_count == 0
        assert eval_run.pass_count == 0
        assert eval_run.fail_count == 0
        assert eval_run.error_count == 0

    async def test_terminal_eval_skipped_on_redispatch(
        self,
        session: AsyncSession,
        workspace: Workspace,
        mocker: MockerFixture,
    ) -> None:
        # An eval already marked ``succeeded`` should be a no-op
        # on re-dispatch (Dramatiq is at-least-once; we don't
        # want a retry to re-run the eval and double the
        # pass/fail counters).
        version = await _seed_workflow_version(session, workspace)
        dataset = Dataset(workspace_id=workspace.id, name="ds")
        session.add(dataset)
        await session.flush()

        eval_run = EvalRun(
            workspace_id=workspace.id,
            dataset_id=dataset.id,
            workflow_version_id=version.id,
            status=EvalRunStatus.succeeded,
            case_count=42,
            pass_count=42,
        )
        session.add(eval_run)
        await session.flush()

        class _Ctx:
            async def __aenter__(self) -> AsyncSession:
                return session

            async def __aexit__(self, *args: object) -> None:
                return None

        mocker.patch.object(eval_workers, "AsyncSessionMaker", return_value=_Ctx())

        await eval_workers.run_eval(eval_run.id)
        await session.refresh(eval_run)

        # Counters untouched — the actor saw the terminal status
        # and bailed.
        assert eval_run.case_count == 42
        assert eval_run.pass_count == 42
