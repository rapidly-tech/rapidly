"""Run lifecycle: list, get, cancel.

Run-triggering (``POST /api/v1/workflows/{id}/runs``) lives on the
route layer and currently returns 501 — the actual execution
engine that walks the DAG and writes status transitions ships in
M4.2. This module captures the read + cancel surface only so the
M5 UI can build against a real route shape.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.agents.run.queries import RunRepository
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import NotPermitted, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import Run, RunStatus
from rapidly.models.agent_run import TERMINAL_RUN_STATUSES
from rapidly.postgres import AsyncReadSession, AsyncSession


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> Run | None:
    repo = RunRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(Run.id == id)
    return await repo.get_one_or_none(stmt)


async def get_or_raise(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> Run:
    run = await get(session, auth_subject, id)
    if run is None:
        raise ResourceNotFound("Run not found.")
    return run


async def list_runs(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workflow_version_id: UUID | None = None,
    status: RunStatus | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[Run], int]:
    repo = RunRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if workflow_version_id is not None:
        statement = statement.where(Run.workflow_version_id == workflow_version_id)
    if status is not None:
        statement = statement.where(Run.status == status)
    return await paginate(session, statement, pagination=pagination)


async def cancel(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    run: Run,
) -> Run:
    """Flip a non-terminal run to ``cancelled``.

    The engine (M4.2) polls a Redis pubsub channel between node
    calls and exits cleanly on receipt. For this scaffold PR the
    cancel just writes the status; M4.2 wires the pubsub publish.

    Refuses to cancel an already-terminal run with NotPermitted so
    the caller sees a clear 403 (not a silent no-op).
    """
    if run.status in TERMINAL_RUN_STATUSES:
        raise NotPermitted(f"Run already in terminal status {run.status.value}.")
    run.status = RunStatus.cancelled
    run.completed_at = now_utc()
    await session.flush()
    # M4.2 will publish a redis cancel signal here.
    return run
