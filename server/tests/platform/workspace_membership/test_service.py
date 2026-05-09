"""Tests for user-workspace membership service."""

from typing import Any
from uuid import uuid4

import pytest

from rapidly.models import Account, User, Workspace, WorkspaceMembership
from rapidly.platform.workspace_membership import (
    actions as workspace_membership_service,
)
from rapidly.platform.workspace_membership.actions import (
    CannotRemoveWorkspaceAdmin,
    UserNotMemberOfWorkspace,
    WorkspaceNotFound,
)


@pytest.mark.asyncio
class TestRemoveMemberSafe:
    async def test_remove_member_success(
        self,
        session: Any,
        workspace: Workspace,
        user: User,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        # Test successful member removal
        await workspace_membership_service.remove_member_safe(
            session, user.id, workspace.id
        )

        # Verify the member was soft deleted
        user_org = await workspace_membership_service.get_by_user_and_org(
            session, user.id, workspace.id
        )
        assert user_org is None

    async def test_remove_member_workspace_not_found(
        self,
        session: Any,
        user: User,
    ) -> None:
        # Test with non-existent workspace
        non_existent_org_id = uuid4()

        with pytest.raises(WorkspaceNotFound) as exc_info:
            await workspace_membership_service.remove_member_safe(
                session, user.id, non_existent_org_id
            )

        assert exc_info.value.workspace_id == non_existent_org_id

    async def test_remove_member_user_not_member(
        self,
        session: Any,
        workspace: Workspace,
        user: User,
    ) -> None:
        # Test with user who is not a member
        with pytest.raises(UserNotMemberOfWorkspace) as exc_info:
            await workspace_membership_service.remove_member_safe(
                session, user.id, workspace.id
            )

        assert exc_info.value.user_id == user.id
        assert exc_info.value.workspace_id == workspace.id

    async def test_remove_member_cannot_remove_admin(
        self,
        session: Any,
        workspace_account: Account,
        workspace: Workspace,
        user: User,
        save_fixture: Any,
    ) -> None:
        # Create user workspace relationship for admin
        from rapidly.core.utils import now_utc
        from rapidly.models import WorkspaceMembership

        # The user fixture becomes the admin through workspace_account fixture
        admin_user_org = WorkspaceMembership(
            user_id=user.id,
            workspace_id=workspace.id,
            created_at=now_utc(),
        )
        await save_fixture(admin_user_org)

        # Test trying to remove workspace admin
        with pytest.raises(CannotRemoveWorkspaceAdmin) as exc_info:
            await workspace_membership_service.remove_member_safe(
                session, user.id, workspace.id
            )

        assert exc_info.value.user_id == user.id
        assert exc_info.value.workspace_id == workspace.id

    async def test_remove_member_non_admin_with_account(
        self,
        session: Any,
        workspace_account: Account,
        workspace: Workspace,
        user_second: User,
        save_fixture: Any,
    ) -> None:
        # Create user workspace relationship for non-admin user
        from rapidly.core.utils import now_utc
        from rapidly.models import WorkspaceMembership

        user_org_relation = WorkspaceMembership(
            user_id=user_second.id,
            workspace_id=workspace.id,
            created_at=now_utc(),
        )
        await save_fixture(user_org_relation)

        # Test removing a non-admin member from workspace with account
        await workspace_membership_service.remove_member_safe(
            session, user_second.id, workspace.id
        )

        # Verify the member was soft deleted
        user_org: (
            WorkspaceMembership | None
        ) = await workspace_membership_service.get_by_user_and_org(
            session, user_second.id, workspace.id
        )
        assert user_org is None

    async def test_remove_member_no_account(
        self,
        session: Any,
        workspace: Workspace,
        user: User,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        # Test removing member from workspace without account (no admin check)
        await workspace_membership_service.remove_member_safe(
            session, user.id, workspace.id
        )

        # Verify the member was soft deleted
        user_org = await workspace_membership_service.get_by_user_and_org(
            session, user.id, workspace.id
        )
        assert user_org is None


@pytest.mark.asyncio
class TestRemoveMember:
    async def test_remove_member_soft_delete(
        self,
        session: Any,
        workspace: Workspace,
        user: User,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        # Test that remove_member performs soft delete
        await workspace_membership_service.remove_member(session, user.id, workspace.id)

        # Verify the member was soft deleted (not returned by get_by_user_and_org)
        user_org = await workspace_membership_service.get_by_user_and_org(
            session, user.id, workspace.id
        )
        assert user_org is None

        # But the record still exists in DB with deleted_at set
        from rapidly.postgres import sql

        result = await session.execute(
            sql.select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == workspace.id,
            )
        )
        deleted_user_org: WorkspaceMembership | None = result.scalar_one_or_none()
        assert deleted_user_org is not None
        assert deleted_user_org.deleted_at is not None


@pytest.mark.asyncio
class TestListByOrg:
    async def test_list_by_org_excludes_deleted(
        self,
        session: Any,
        workspace: Workspace,
        user: User,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        # Initially should return the member
        members = await workspace_membership_service.list_by_org(session, workspace.id)
        assert len(members) == 1
        assert members[0].user_id == user.id

        # After soft delete, should not return the member
        await workspace_membership_service.remove_member(session, user.id, workspace.id)

        members = await workspace_membership_service.list_by_org(session, workspace.id)
        assert len(members) == 0
