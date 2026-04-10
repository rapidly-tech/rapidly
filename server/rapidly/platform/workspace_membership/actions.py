"""User-workspace membership service: invitations, roles, and transfers.

Manages the ``WorkspaceMembership`` join records that associate users with
workspaces, including invitation creation / acceptance, role
assignment, and ownership transfer.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.errors import RapidlyError
from rapidly.models import WorkspaceMembership
from rapidly.platform.workspace_membership.queries import WorkspaceMembershipRepository
from rapidly.postgres import AsyncReadSession, AsyncSession


class WorkspaceMembershipError(RapidlyError): ...


class WorkspaceNotFound(WorkspaceMembershipError):
    def __init__(self, workspace_id: UUID) -> None:
        self.workspace_id = workspace_id
        message = f"Workspace with id {workspace_id} not found."
        super().__init__(message, 404)


class UserNotMemberOfWorkspace(WorkspaceMembershipError):
    def __init__(self, user_id: UUID, workspace_id: UUID) -> None:
        self.user_id = user_id
        self.workspace_id = workspace_id
        message = f"User with id {user_id} is not a member of workspace {workspace_id}."
        super().__init__(message, 404)


class CannotRemoveWorkspaceAdmin(WorkspaceMembershipError):
    def __init__(self, user_id: UUID, workspace_id: UUID) -> None:
        self.user_id = user_id
        self.workspace_id = workspace_id
        message = f"Cannot remove user {user_id} - they are the admin of workspace {workspace_id}."
        super().__init__(message, 403)


# ── Reads ──


async def list_by_workspace(
    session: AsyncReadSession, workspace_id: UUID
) -> Sequence[WorkspaceMembership]:
    repo = WorkspaceMembershipRepository.from_session(session)
    return await repo.list_by_workspace(workspace_id)


# Backwards-compatible alias (renamed from list_by_org → list_by_workspace)
list_by_org = list_by_workspace


async def get_member_count(session: AsyncReadSession, workspace_id: UUID) -> int:
    """Get the count of active members in an workspace."""
    repo = WorkspaceMembershipRepository.from_session(session)
    return await repo.get_member_count(workspace_id)


async def list_by_user_id(
    session: AsyncSession, user_id: UUID
) -> Sequence[WorkspaceMembership]:
    repo = WorkspaceMembershipRepository.from_session(session)
    return await repo.list_by_user_id(user_id)


async def get_workspace_membership_count(session: AsyncSession, user_id: UUID) -> int:
    repo = WorkspaceMembershipRepository.from_session(session)
    return await repo.get_workspace_membership_count(user_id)


async def get_by_user_and_org(
    session: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
) -> WorkspaceMembership | None:
    repo = WorkspaceMembershipRepository.from_session(session)
    return await repo.get_by_user_and_org(user_id, workspace_id)


# ── Membership ──


async def remove_member(
    session: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
) -> None:
    repo = WorkspaceMembershipRepository.from_session(session)
    await repo.remove_member(user_id, workspace_id)


async def remove_member_safe(
    session: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
) -> None:
    """
    Safely remove a member from an workspace.

    Raises:
        WorkspaceNotFound: If the workspace doesn't exist
        UserNotMemberOfWorkspace: If the user is not a member of the workspace
        CannotRemoveWorkspaceAdmin: If the user is the workspace admin
    """
    from rapidly.platform.workspace.queries import WorkspaceRepository

    org_repo = WorkspaceRepository.from_session(session)
    workspace = await org_repo.get_by_id(workspace_id)

    if not workspace:
        raise WorkspaceNotFound(workspace_id)

    # Check if user is actually a member
    user_org = await get_by_user_and_org(session, user_id, workspace_id)
    if not user_org:
        raise UserNotMemberOfWorkspace(user_id, workspace_id)

    # Check if the user is the workspace admin
    if workspace.account_id:
        admin_user = await org_repo.get_admin_user(session, workspace)
        if admin_user and admin_user.id == user_id:
            raise CannotRemoveWorkspaceAdmin(user_id, workspace_id)

    # Remove the member
    await remove_member(session, user_id, workspace_id)
