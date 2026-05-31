"""Project-level role checks for write operations.

Workspace membership lets a user *see* projects in their workspace, but
mutating a project requires a per-project role.  Workspace-scoped tokens
bypass this gate: a workspace token implicitly carries admin authority
over every project it can read.
"""

from uuid import UUID

from sqlalchemy import select

from rapidly.errors import NotPermitted
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Project, ProjectMember, ProjectMemberRole
from rapidly.postgres import AsyncReadSession, AsyncSession


async def get_member_role(
    session: AsyncSession | AsyncReadSession,
    project_id: UUID,
    user_id: UUID,
) -> ProjectMemberRole | None:
    """Return the user's role on the project, or ``None`` if not a member."""
    stmt = select(ProjectMember.role).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
        ProjectMember.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def require_role(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    project: Project,
    *,
    minimum: ProjectMemberRole,
) -> None:
    """Raise ``NotPermitted`` unless the caller meets the project-role floor.

    Workspace-scoped tokens are admins of every project in their workspace.
    User principals must hold a ProjectMember role at or above ``minimum``.
    """
    # Workspace tokens scoped to this project's workspace pass.
    if is_workspace_principal(auth_subject):
        if auth_subject.subject.id != project.workspace_id:
            raise NotPermitted("Workspace mismatch.")
        return

    if not is_user_principal(auth_subject):
        raise NotPermitted("Unsupported auth subject.")

    role = await get_member_role(session, project.id, auth_subject.subject.id)
    if role is None:
        raise NotPermitted("You are not a member of this project.")

    if not _role_satisfies(role, minimum):
        raise NotPermitted(
            f"This action requires the '{minimum.value}' project role or higher."
        )


_ROLE_RANK: dict[ProjectMemberRole, int] = {
    ProjectMemberRole.guest: 0,
    ProjectMemberRole.member: 1,
    ProjectMemberRole.admin: 2,
}


def _role_satisfies(role: ProjectMemberRole, minimum: ProjectMemberRole) -> bool:
    return _ROLE_RANK[role] >= _ROLE_RANK[minimum]
