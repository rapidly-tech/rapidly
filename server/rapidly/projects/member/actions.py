"""Project-membership lifecycle: list, add, update role, remove.

Mutating membership requires the ``admin`` project role.  Workspace-scoped
tokens bypass the role gate via ``require_role`` (they're implicit admins
of every project in their workspace).
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
    ProjectMember,
    ProjectMemberRole,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.member.ordering import ProjectMemberSortProperty
from rapidly.projects.member.queries import ProjectMemberRepository
from rapidly.projects.member.types import ProjectMemberCreate, ProjectMemberUpdate
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectMember | None:
    repo = ProjectMemberRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectMember.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_project(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectMemberSortProperty]],
) -> tuple[Sequence[ProjectMember], int]:
    repo = ProjectMemberRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectMember.project_id.in_(project_id))
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectMemberCreate,
) -> ProjectMember:
    project = await _ensure_admin(session, auth_subject, data.project_id)
    await _ensure_user_in_workspace(session, project.workspace_id, data.user_id)

    repo = ProjectMemberRepository.from_session(session)
    existing = await repo.get_by_project_and_user(project.id, data.user_id)
    if existing is not None:
        raise ResourceAlreadyExists("User is already a member of this project.")

    member = ProjectMember(
        project_id=project.id,
        user_id=data.user_id,
        role=data.role,
    )
    return await repo.create(member, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    member: ProjectMember,
    data: ProjectMemberUpdate,
) -> ProjectMember:
    await _ensure_admin(session, auth_subject, member.project_id)

    update_dict = data.model_dump(exclude_unset=True)
    if "role" in update_dict and update_dict["role"] != member.role:
        await _ensure_not_last_admin(session, member)

    if not update_dict:
        return member
    repo = ProjectMemberRepository.from_session(session)
    return await repo.update(member, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    member: ProjectMember,
) -> None:
    await _ensure_admin(session, auth_subject, member.project_id)
    await _ensure_not_last_admin(session, member)
    repo = ProjectMemberRepository.from_session(session)
    await repo.soft_delete(member)


async def _ensure_admin(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project_id: UUID,
) -> Project:
    project_repo = ProjectRepository.from_session(session)
    project = await project_repo.get_one_or_none(
        project_repo.get_readable_statement(auth_subject).where(
            project_repo.model.id == project_id
        )
    )
    if project is None:
        raise ResourceNotFound("Project not found.")
    await require_role(session, auth_subject, project, minimum=ProjectMemberRole.admin)
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
        raise BadRequest("User is not a member of this project's workspace.")


async def _ensure_not_last_admin(session: AsyncSession, member: ProjectMember) -> None:
    """Block removing or demoting the project's only remaining admin.

    Why: a project must always have at least one admin so that future
    membership changes are possible.  Without this check, a single admin
    could demote themselves and lock the project's roster.
    """
    if member.role is not ProjectMemberRole.admin:
        return
    stmt = select(ProjectMember.id).where(
        ProjectMember.project_id == member.project_id,
        ProjectMember.role == ProjectMemberRole.admin,
        ProjectMember.deleted_at.is_(None),
        ProjectMember.id != member.id,
    )
    if (await session.execute(stmt)).first() is None:
        raise BadRequest("A project must have at least one admin.")
