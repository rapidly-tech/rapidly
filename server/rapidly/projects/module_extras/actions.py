"""Module-member + module-link lifecycle actions.

Both flows share the same project-membership gate: a caller must hold
the project's ``member`` role (workspace tokens bypass via
``require_role``) to read or mutate.  Adding someone to a module's
roster requires that user to already be a workspace member — same
guard ``rapidly/projects/member`` uses for project roster adds.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import BadRequest, ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    Project,
    ProjectMemberRole,
    ProjectModule,
    ProjectModuleLink,
    ProjectModuleMember,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.module_extras.ordering import ModuleExtrasSortProperty
from rapidly.projects.module_extras.queries import (
    ProjectModuleLinkRepository,
    ProjectModuleMemberRepository,
)
from rapidly.projects.module_extras.types import (
    ProjectModuleLinkCreate,
    ProjectModuleLinkUpdate,
    ProjectModuleMemberCreate,
)
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository

# ── Members ──────────────────────────────────────────────────────────


async def get_member(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectModuleMember | None:
    repo = ProjectModuleMemberRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectModuleMember.id == id)
    return await repo.get_one_or_none(stmt)


async def list_members(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    module_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ModuleExtrasSortProperty]],
) -> tuple[Sequence[ProjectModuleMember], int]:
    await _readable_module(session, auth_subject, module_id)
    repo = ProjectModuleMemberRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        ProjectModuleMember.module_id == module_id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def add_member(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectModuleMemberCreate,
) -> ProjectModuleMember:
    module = await _readable_module(session, auth_subject, data.module_id)
    project = await _ensure_member(session, auth_subject, module)
    await _ensure_user_in_workspace(session, project.workspace_id, data.user_id)

    repo = ProjectModuleMemberRepository.from_session(session)
    existing = await repo.get_for_module_and_user(data.module_id, data.user_id)
    if existing is not None:
        raise ResourceAlreadyExists("User is already a member of this module.")

    member = ProjectModuleMember(module_id=data.module_id, user_id=data.user_id)
    return await repo.create(member, flush=True)


async def remove_member(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    member: ProjectModuleMember,
) -> None:
    module = await _readable_module(session, auth_subject, member.module_id)
    await _ensure_member(session, auth_subject, module)
    repo = ProjectModuleMemberRepository.from_session(session)
    await repo.soft_delete(member)


# ── Links ────────────────────────────────────────────────────────────


async def get_link(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectModuleLink | None:
    repo = ProjectModuleLinkRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectModuleLink.id == id)
    return await repo.get_one_or_none(stmt)


async def list_links(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    module_id: UUID,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ModuleExtrasSortProperty]],
) -> tuple[Sequence[ProjectModuleLink], int]:
    await _readable_module(session, auth_subject, module_id)
    repo = ProjectModuleLinkRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        ProjectModuleLink.module_id == module_id
    )
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def create_link(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectModuleLinkCreate,
) -> ProjectModuleLink:
    module = await _readable_module(session, auth_subject, data.module_id)
    await _ensure_member(session, auth_subject, module)

    actor_id = (
        auth_subject.subject.id if isinstance(auth_subject.subject, User) else None
    )
    repo = ProjectModuleLinkRepository.from_session(session)
    link = ProjectModuleLink(
        module_id=data.module_id,
        created_by_id=actor_id,
        url=str(data.url),
        title=data.title,
    )
    return await repo.create(link, flush=True)


async def update_link(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    link: ProjectModuleLink,
    data: ProjectModuleLinkUpdate,
) -> ProjectModuleLink:
    module = await _readable_module(session, auth_subject, link.module_id)
    await _ensure_member(session, auth_subject, module)

    update_dict: dict[str, str | None] = {}
    if data.url is not None:
        update_dict["url"] = str(data.url)
    raw = data.model_dump(exclude_unset=True)
    if "title" in raw:
        update_dict["title"] = data.title

    if not update_dict:
        return link
    repo = ProjectModuleLinkRepository.from_session(session)
    return await repo.update(link, update_dict=update_dict)


async def delete_link(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    link: ProjectModuleLink,
) -> None:
    module = await _readable_module(session, auth_subject, link.module_id)
    await _ensure_member(session, auth_subject, module)
    repo = ProjectModuleLinkRepository.from_session(session)
    await repo.soft_delete(link)


# ── Helpers ──────────────────────────────────────────────────────────


async def _readable_module(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    module_id: UUID,
) -> ProjectModule:
    """Resolve the module through the workspace boundary."""
    if isinstance(auth_subject.subject, User):
        user = auth_subject.subject
        stmt = (
            select(ProjectModule)
            .join(Project, Project.id == ProjectModule.project_id)
            .where(
                ProjectModule.id == module_id,
                Project.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                ),
            )
        )
    elif isinstance(auth_subject.subject, Workspace):
        stmt = (
            select(ProjectModule)
            .join(Project, Project.id == ProjectModule.project_id)
            .where(
                ProjectModule.id == module_id,
                Project.workspace_id == auth_subject.subject.id,
            )
        )
    else:
        raise ResourceNotFound("Module not found.")

    result = await session.execute(stmt)
    module = result.scalar_one_or_none()
    if module is None:
        raise ResourceNotFound("Module not found.")
    return module


async def _ensure_member(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    module: ProjectModule,
) -> Project:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == module.project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.member)
    return project


async def _ensure_user_in_workspace(
    session: AsyncSession, workspace_id: UUID, user_id: UUID
) -> None:
    stmt = select(WorkspaceMembership.user_id).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.deleted_at.is_(None),
    )
    if (await session.execute(stmt)).first() is None:
        raise BadRequest("User is not a member of this module's workspace.")
