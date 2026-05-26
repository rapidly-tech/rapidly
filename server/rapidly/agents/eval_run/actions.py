"""EvalRun lifecycle: trigger, list, get."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.agents.eval_run.queries import (
    EvalRunCaseRepository,
    EvalRunRepository,
)
from rapidly.agents.eval_run.types import EvalRunTrigger
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    EvalRun,
    EvalRunCase,
    Workflow,
    WorkflowVersion,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.worker import dispatch_task


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> EvalRun | None:
    repo = EvalRunRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(EvalRun.id == id)
    return await repo.get_one_or_none(stmt)


async def get_or_raise(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> EvalRun:
    eval_run = await get(session, auth_subject, id)
    if eval_run is None:
        raise ResourceNotFound("EvalRun not found.")
    return eval_run


async def list_eval_runs(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    dataset_id: UUID | None = None,
    workflow_version_id: UUID | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[EvalRun], int]:
    repo = EvalRunRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).order_by(
        EvalRun.created_at.desc()
    )
    if dataset_id is not None:
        statement = statement.where(EvalRun.dataset_id == dataset_id)
    if workflow_version_id is not None:
        statement = statement.where(EvalRun.workflow_version_id == workflow_version_id)
    return await paginate(session, statement, pagination=pagination)


async def list_cases(
    session: AsyncReadSession,
    eval_run: EvalRun,
) -> Sequence[EvalRunCase]:
    """List all case results for an eval run, oldest-first.

    No pagination — a dataset's case count is small enough
    that the full list fits comfortably in one response.
    Large eval runs (1000+ cases) are out of v1 scope; if they
    materialise we'll add pagination + a streaming export.
    """
    repo = EvalRunCaseRepository.from_session(session)
    stmt = repo.for_eval_run(eval_run.id).order_by(EvalRunCase.created_at.asc())
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def trigger(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: EvalRunTrigger,
) -> EvalRun:
    """Create an EvalRun + dispatch the runner actor.

    The dataset + workflow_version must be in the same workspace,
    and the caller must be able to read both (the readable
    statement on each does the check). The eval row is created
    in ``pending`` state — the actor flips it to ``running`` on
    pickup. Returning immediately (HTTP 202) keeps the API
    responsive even when the workspace has 500-case datasets.
    """
    # Verify caller can read the dataset (raises 404 otherwise).
    from rapidly.agents.dataset.actions import get_dataset_or_raise

    dataset = await get_dataset_or_raise(session, auth_subject, data.dataset_id)

    # Verify caller can read the workflow_version + it's in the
    # same workspace as the dataset. We don't have a
    # workflow_version_actions module yet, so do the join inline.
    version = (
        await session.execute(
            select(WorkflowVersion)
            .join(Workflow, Workflow.id == WorkflowVersion.workflow_id)
            .where(
                WorkflowVersion.id == data.workflow_version_id,
                Workflow.workspace_id == dataset.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise ResourceNotFound("WorkflowVersion not found in this workspace.")

    repo = EvalRunRepository.from_session(session)
    record = EvalRun(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.id,
        workflow_version_id=version.id,
        assertion_strategy=data.assertion_strategy,
    )
    created = await repo.create(record, flush=True)
    dispatch_task("agents.eval.run", eval_run_id=created.id)
    return created
