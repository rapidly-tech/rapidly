"""Project lifecycle: list, get, create, update, archive, delete."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import NotPermitted, ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Project, ProjectMember, ProjectMemberRole
from rapidly.platform.workspace.queries import WorkspaceRepository
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.project.access import require_role
from rapidly.projects.project.ordering import ProjectSortProperty
from rapidly.projects.project.queries import ProjectRepository
from rapidly.projects.project.types import ProjectCreate, ProjectUpdate


class ProjectIdentifierTaken(ResourceAlreadyExists):
    def __init__(self, identifier: str) -> None:
        super().__init__(
            f"A project with identifier '{identifier}' already exists in this workspace.",
        )


class ProjectSlugTaken(ResourceAlreadyExists):
    def __init__(self, slug: str) -> None:
        super().__init__(
            f"A project with slug '{slug}' already exists in this workspace.",
        )


# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> Project | None:
    repo = ProjectRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(Project.id == id)
    return await repo.get_one_or_none(stmt)


async def list(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: Sequence[UUID] | None = None,
    include_archived: bool = False,
    name: str | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectSortProperty]],
) -> tuple[Sequence[Project], int]:
    repo = ProjectRepository.from_session(session)
    statement: Select[tuple[Project]] = repo.get_readable_statement(auth_subject)

    if workspace_id is not None:
        statement = statement.where(Project.workspace_id.in_(workspace_id))
    if not include_archived:
        statement = statement.where(Project.archived_at.is_(None))
    if name is not None and name.strip():
        # Case-insensitive substring match on display name.  ``%``/``_``
        # in the input are escaped so users cannot smuggle wildcards
        # past the intended substring semantics.
        escaped = (
            name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        statement = statement.where(Project.name.ilike(f"%{escaped}%", escape="\\"))

    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workspace_id: UUID,
    data: ProjectCreate,
) -> Project:
    workspace_repo = WorkspaceRepository.from_session(session)

    owner_id: UUID
    if is_user_principal(auth_subject):
        user = auth_subject.subject
        workspace = await workspace_repo.get_accessible_by_id(workspace_id, user.id)
        if workspace is None:
            raise ResourceNotFound("Workspace not found.")
        owner_id = user.id
    elif is_workspace_principal(auth_subject):
        workspace = auth_subject.subject
        if workspace.id != workspace_id:
            raise NotPermitted("Workspace mismatch.")
        owner_id = workspace.id
    else:
        raise NotPermitted("Unsupported auth subject.")

    repo = ProjectRepository.from_session(session)

    if await repo.get_by_identifier(workspace_id, data.identifier) is not None:
        raise ProjectIdentifierTaken(data.identifier)
    if await repo.get_by_slug(workspace_id, data.slug) is not None:
        raise ProjectSlugTaken(data.slug)

    project = Project(
        workspace_id=workspace_id,
        owner_id=owner_id,
        name=data.name,
        identifier=data.identifier,
        slug=data.slug,
        description=data.description,
        visibility=data.visibility,
        emoji=data.emoji,
        color=data.color,
        cover_image_url=data.cover_image_url,
        is_cycles_enabled=data.is_cycles_enabled,
        is_modules_enabled=data.is_modules_enabled,
        is_views_enabled=data.is_views_enabled,
        is_pages_enabled=data.is_pages_enabled,
        is_intake_enabled=data.is_intake_enabled,
    )
    project = await repo.create(project, flush=True)

    # The creator joins the project as an admin if they are a real user.
    if is_user_principal(auth_subject):
        session.add(
            ProjectMember(
                project_id=project.id,
                user_id=auth_subject.subject.id,
                role=ProjectMemberRole.admin,
            )
        )
        await session.flush()

    return project


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project: Project,
    data: ProjectUpdate,
) -> Project:
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)
    repo = ProjectRepository.from_session(session)
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return project
    return await repo.update(project, update_dict=update_dict)


async def archive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project: Project,
) -> Project:
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)
    repo = ProjectRepository.from_session(session)
    return await repo.update(project, update_dict={"archived_at": now_utc()})


async def unarchive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project: Project,
) -> Project:
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)
    repo = ProjectRepository.from_session(session)
    return await repo.update(project, update_dict={"archived_at": None})


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project: Project,
) -> None:
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)
    repo = ProjectRepository.from_session(session)
    await repo.soft_delete(project)
