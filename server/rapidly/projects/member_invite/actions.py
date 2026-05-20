"""Project-member-invite lifecycle: create, list, accept, decline, revoke.

Why a separate model from ProjectMember:
- An invite carries *consent state*; a membership doesn't.  Without
  this split, accepting/declining can't be distinguished from being
  added directly (which is how #698 lands today).
- Multiple lifecycle transitions (pending → accepted | declined |
  revoked) make the state machine clearer when it lives on its own
  row rather than being a flag on the membership.

The token is the secret an invitee presents to accept. Generated
with ``secrets.token_urlsafe`` so it's URL-safe and contains
~256 bits of entropy at the default length.
"""

import secrets
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.ordering import Sorting
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import (
    BadRequest,
    NotPermitted,
    ResourceAlreadyExists,
    ResourceNotFound,
)
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import (
    Project,
    ProjectMember,
    ProjectMemberInvite,
    ProjectMemberInviteStatus,
    ProjectMemberRole,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.projects.member_invite.ordering import ProjectMemberInviteSortProperty
from rapidly.projects.member_invite.queries import ProjectMemberInviteRepository
from rapidly.projects.member_invite.types import ProjectMemberInviteCreate
from rapidly.projects.project.access import require_role
from rapidly.projects.project.queries import ProjectRepository

# ── Reads ──


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> ProjectMemberInvite | None:
    repo = ProjectMemberInviteRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(ProjectMemberInvite.id == id)
    return await repo.get_one_or_none(stmt)


async def list_for_project(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    project_id: Sequence[UUID] | None = None,
    invitee_id: UUID | None = None,
    status: ProjectMemberInviteStatus | None = None,
    pagination: PaginationParams,
    sorting: Sequence[Sorting[ProjectMemberInviteSortProperty]],
) -> tuple[Sequence[ProjectMemberInvite], int]:
    repo = ProjectMemberInviteRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if project_id is not None:
        statement = statement.where(ProjectMemberInvite.project_id.in_(project_id))
    if invitee_id is not None:
        statement = statement.where(ProjectMemberInvite.invitee_id == invitee_id)
    if status is not None:
        statement = statement.where(ProjectMemberInvite.status == status)
    statement = repo.apply_sorting(statement, sorting)
    return await paginate(session, statement, pagination=pagination)


# ── Writes ──


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: ProjectMemberInviteCreate,
) -> ProjectMemberInvite:
    """Issue an invite. Admin-only; invitee must be in the workspace."""
    project = await _ensure_admin(session, auth_subject, data.project_id)

    await _ensure_user_in_workspace(session, project.workspace_id, data.invitee_id)

    # Already a member? No point inviting.
    if await _existing_membership(session, project.id, data.invitee_id) is not None:
        raise ResourceAlreadyExists("User is already a member of this project.")

    repo = ProjectMemberInviteRepository.from_session(session)
    existing = await repo.get_pending_for_user_and_project(project.id, data.invitee_id)
    if existing is not None:
        raise ResourceAlreadyExists("A pending invite for this user already exists.")

    invite = ProjectMemberInvite(
        project_id=project.id,
        invitee_id=data.invitee_id,
        invited_by_id=(
            auth_subject.subject.id if isinstance(auth_subject.subject, User) else None
        ),
        role=data.role.value,
        token=secrets.token_urlsafe(32),
        status=ProjectMemberInviteStatus.pending,
    )
    return await repo.create(invite, flush=True)


async def accept(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    *,
    token: str,
) -> ProjectMember:
    """Invitee accepts an invite using its token.

    Why look up by token: the route never reveals the invite ID to
    the invitee in the email/notification — only the token — so the
    accept endpoint must find the invite by that opaque string.
    The caller must be the invitee, regardless of token possession.
    """
    repo = ProjectMemberInviteRepository.from_session(session)
    invite = await repo.get_by_token(token)
    if invite is None or invite.status != ProjectMemberInviteStatus.pending:
        raise ResourceNotFound()

    if invite.invitee_id != auth_subject.subject.id:
        # Token possession alone is not enough — the invitee identity
        # must match.  Without this check, a leaked token would let
        # any caller join the project.
        raise NotPermitted()

    existing = await _existing_membership(session, invite.project_id, invite.invitee_id)
    if existing is not None:
        # Race: someone added them directly between invite creation
        # and acceptance.  Mark the invite accepted anyway and return
        # the existing membership.
        await repo.update(
            invite,
            update_dict={
                "status": ProjectMemberInviteStatus.accepted,
                "accepted_at": now_utc(),
            },
        )
        return existing

    member = ProjectMember(
        project_id=invite.project_id,
        user_id=invite.invitee_id,
        role=ProjectMemberRole(invite.role),
    )
    session.add(member)
    await session.flush()
    await repo.update(
        invite,
        update_dict={
            "status": ProjectMemberInviteStatus.accepted,
            "accepted_at": now_utc(),
        },
    )
    return member


async def decline(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User],
    invite: ProjectMemberInvite,
) -> ProjectMemberInvite:
    if invite.invitee_id != auth_subject.subject.id:
        raise NotPermitted()
    if invite.status != ProjectMemberInviteStatus.pending:
        raise BadRequest("Invite is not in a pending state.")

    repo = ProjectMemberInviteRepository.from_session(session)
    return await repo.update(
        invite,
        update_dict={
            "status": ProjectMemberInviteStatus.declined,
            "declined_at": now_utc(),
        },
    )


async def revoke(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    invite: ProjectMemberInvite,
) -> ProjectMemberInvite:
    """Admin retracts a pending invite."""
    await _ensure_admin(session, auth_subject, invite.project_id)
    if invite.status != ProjectMemberInviteStatus.pending:
        raise BadRequest("Invite is not in a pending state.")

    repo = ProjectMemberInviteRepository.from_session(session)
    return await repo.update(
        invite,
        update_dict={
            "status": ProjectMemberInviteStatus.revoked,
            "revoked_at": now_utc(),
        },
    )


# ── Helpers ──


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


async def _existing_membership(
    session: AsyncSession | AsyncReadSession,
    project_id: UUID,
    user_id: UUID,
) -> ProjectMember | None:
    """Find an active membership row directly — avoids depending on the
    ``project_member`` submodule's repository, which isn't on main yet
    (it ships in PR #698).  Once that lands, this helper can be
    replaced with ``ProjectMemberRepository.get_by_project_and_user``.
    """
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
        ProjectMember.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()
