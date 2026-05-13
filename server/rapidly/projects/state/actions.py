"""Project state lifecycle: list, get, create, update, delete."""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import ProjectMemberRole, ProjectState
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.state.ordering import ProjectStateSortProperty
from rapidly.projects.state.queries import ProjectStateRepository
from rapidly.projects.state.types import ProjectStateCreate, ProjectStateUpdate


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectState | None:
    repo = ProjectStateRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectState.id == id)
    return await repo.get_one_or_none(stmt)


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectStateSortProperty]],
) -> tuple[Sequence[ProjectState], int]:
    repo = ProjectStateRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectState.project_id.in_(project_id))
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectStateCreate,
) -> ProjectState:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == data.project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")

    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)

    repo = ProjectStateRepository.from_session(session)
    if await repo.get_by_name(data.project_id, data.name) is not None:
        raise ResourceAlreadyExists(
            f"A state named '{data.name}' already exists in this project."
        )

    state = ProjectState(
        project_id=data.project_id,
        name=data.name,
        description=data.description,
        color=data.color,
        group=data.group,
        sequence=data.sequence,
        is_default=data.is_default,
    )
    return await repo.create(state, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    state: ProjectState,
    data: ProjectStateUpdate,
) -> ProjectState:
    await _ensure_member(session, auth_subject, state.project_id)
    repo = ProjectStateRepository.from_session(session)
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return state
    return await repo.update(state, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    state: ProjectState,
) -> None:
    await _ensure_member(session, auth_subject, state.project_id)
    repo = ProjectStateRepository.from_session(session)
    await repo.soft_delete(state)


async def _ensure_member(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project_id: UUID,
) -> None:
    """Re-fetch the parent project and require ``member`` role for write ops."""
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)
