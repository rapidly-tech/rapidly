"""Workflow lifecycle: list, get, create, update, delete.

Versioning, runs, and node-runs ship in follow-up submodules. This
module is the root-entity CRUD only.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.agents.workflow.queries import WorkflowRepository
from rapidly.agents.workflow.types import WorkflowCreate, WorkflowUpdate
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import Workflow
from rapidly.postgres import AsyncReadSession, AsyncSession


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> Workflow | None:
    repo = WorkflowRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(Workflow.id == id)
    return await repo.get_one_or_none(stmt)


async def get_or_raise(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> Workflow:
    workflow = await get(session, auth_subject, id)
    if workflow is None:
        raise ResourceNotFound("Workflow not found.")
    return workflow


async def list_workflows(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: UUID | None = None,
    name: str | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[Workflow], int]:
    repo = WorkflowRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(Workflow.project_id == project_id)
    if name is not None and name.strip():
        # Same escape pattern as the projects/labels list endpoints.
        # Without escaping, ``name=%`` matches everything and ``name=foo%``
        # behaves as a prefix query, both breaking the documented contract.
        escaped = (
            name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        statement = statement.where(Workflow.name.ilike(f"%{escaped}%", escape="\\"))
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: WorkflowCreate,
) -> Workflow:
    """Create a workflow in its bare state — no version yet.

    The versioning submodule (follow-up PR) is what wires the first
    ``WorkflowVersion`` and updates ``current_version_id``.
    """
    repo = WorkflowRepository.from_session(session)
    record = Workflow(
        workspace_id=data.workspace_id,
        project_id=data.project_id,
        name=data.name,
        description=data.description,
    )
    return await repo.create(record, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workflow: Workflow,
    data: WorkflowUpdate,
) -> Workflow:
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return workflow
    repo = WorkflowRepository.from_session(session)
    return await repo.update(workflow, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workflow: Workflow,
) -> None:
    repo = WorkflowRepository.from_session(session)
    await repo.soft_delete(workflow)
