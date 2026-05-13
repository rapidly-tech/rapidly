"""Project label lifecycle: list, get, create, update, delete."""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import BadRequest, ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import ProjectLabel, ProjectMemberRole
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.label.ordering import ProjectLabelSortProperty
from rapidly.projects.label.queries import ProjectLabelRepository
from rapidly.projects.label.types import ProjectLabelCreate, ProjectLabelUpdate
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectLabel | None:
    repo = ProjectLabelRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectLabel.id == id)
    return await repo.get_one_or_none(stmt)


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    parent_id: UUID | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectLabelSortProperty]],
) -> tuple[Sequence[ProjectLabel], int]:
    repo = ProjectLabelRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectLabel.project_id.in_(project_id))
    if parent_id is not None:
        statement = statement.where(ProjectLabel.parent_id == parent_id)
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectLabelCreate,
) -> ProjectLabel:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == data.project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")

    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)

    repo = ProjectLabelRepository.from_session(session)

    if data.parent_id is not None:
        parent = await repo.get_one_or_none(
            repo.get_readable_statement(auth_subject).where(
                ProjectLabel.id == data.parent_id
            )
        )
        if parent is None:
            raise ResourceNotFound("Parent label not found.")
        if parent.project_id != data.project_id:
            raise BadRequest("Parent label belongs to a different project.")

    if await repo.get_by_name(data.project_id, data.name) is not None:
        raise ResourceAlreadyExists(
            f"A label named '{data.name}' already exists in this project."
        )

    label = ProjectLabel(
        project_id=data.project_id,
        parent_id=data.parent_id,
        name=data.name,
        color=data.color,
        description=data.description,
    )
    return await repo.create(label, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    label: ProjectLabel,
    data: ProjectLabelUpdate,
) -> ProjectLabel:
    await _ensure_member(session, auth_subject, label.project_id)
    repo = ProjectLabelRepository.from_session(session)
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return label
    return await repo.update(label, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    label: ProjectLabel,
) -> None:
    await _ensure_member(session, auth_subject, label.project_id)
    repo = ProjectLabelRepository.from_session(session)
    await repo.soft_delete(label)


async def _ensure_member(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project_id: UUID,
) -> None:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)
