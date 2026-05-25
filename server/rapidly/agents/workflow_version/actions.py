"""WorkflowVersion lifecycle: list, get, create (publish).

Append-only — no update, no delete. The runtime targets specific
versions by id; the editor flips ``Workflow.current_version_id`` to
the version it wants to be the default. A subsequent
``actions.update`` on the workflow performs that flip.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.agents.workflow_version.queries import WorkflowVersionRepository
from rapidly.agents.workflow_version.types import WorkflowVersionCreate
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import WorkflowVersion
from rapidly.postgres import AsyncReadSession, AsyncSession


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkflowVersion | None:
    repo = WorkflowVersionRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(WorkflowVersion.id == id)
    return await repo.get_one_or_none(stmt)


async def get_or_raise(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WorkflowVersion:
    version = await get(session, auth_subject, id)
    if version is None:
        raise ResourceNotFound("Workflow version not found.")
    return version


async def list_for_workflow(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workflow_id: UUID,
    pagination: PaginationParams,
) -> tuple[Sequence[WorkflowVersion], int]:
    repo = WorkflowVersionRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        WorkflowVersion.workflow_id == workflow_id
    )
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    *,
    workflow_id: UUID,
    data: WorkflowVersionCreate,
) -> WorkflowVersion:
    """Publish a new version of a workflow's graph.

    The version_number is server-assigned (next MAX + 1 per
    workflow). The unique constraint on (workflow_id, version_number)
    is the authoritative race-serialiser; concurrent publishes from
    the same workflow will fight for the same number and one will
    IntegrityError. Caller retries.

    NOTE: this action does NOT update Workflow.current_version_id.
    The editor's "publish" button is two actions: create version,
    then PATCH workflow to point at it. Splitting lets the editor
    publish drafts that don't immediately become the runtime
    default.
    """
    repo = WorkflowVersionRepository.from_session(session)
    next_n = await repo.next_version_number(workflow_id)
    record = WorkflowVersion(
        workflow_id=workflow_id,
        version_number=next_n,
        graph_json=data.graph_json,
        created_by_id=auth_subject.subject.id,
    )
    return await repo.create(record, flush=True)
