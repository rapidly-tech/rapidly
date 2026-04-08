"""Tests for user service logic."""

import pytest
from sqlalchemy import select

from rapidly.core.utils import now_utc
from rapidly.models import (
    NotificationRecipient,
    OAuthAccount,
    User,
    Workspace,
    WorkspaceMembership,
)
from rapidly.models.user import OAuthPlatform
from rapidly.platform.user import actions as user_service
from rapidly.platform.user.types import UserDeletionBlockedReason
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import (
    create_notification_recipient,
    create_oauth_account,
)


@pytest.mark.asyncio
class TestCheckCanDelete:
    async def test_can_delete_no_workspaces(
        self,
        session: AsyncSession,
        user: User,
    ) -> None:
        """User with no workspaces can be deleted."""
        result = await user_service.check_can_delete(session, user)

        assert result.blocked_reasons == []
        assert result.blocking_workspaces == []

    async def test_blocked_with_active_workspace(
        self,
        session: AsyncSession,
        user: User,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """User with active workspace cannot be deleted."""
        result = await user_service.check_can_delete(session, user)

        assert UserDeletionBlockedReason.HAS_ACTIVE_WORKSPACES in result.blocked_reasons
        assert len(result.blocking_workspaces) == 1
        assert result.blocking_workspaces[0].id == workspace.id
        assert result.blocking_workspaces[0].slug == workspace.slug

    async def test_can_delete_with_deleted_workspace(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        user: User,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """User can be deleted if all workspaces are soft-deleted."""
        workspace.deleted_at = now_utc()
        await save_fixture(workspace)

        result = await user_service.check_can_delete(session, user)

        assert result.blocked_reasons == []
        assert result.blocking_workspaces == []

    async def test_can_delete_with_deleted_membership(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        user: User,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """User can be deleted if membership is soft-deleted."""
        workspace_membership.deleted_at = now_utc()
        await save_fixture(workspace_membership)

        result = await user_service.check_can_delete(session, user)

        assert result.blocked_reasons == []
        assert result.blocking_workspaces == []


@pytest.mark.asyncio
class TestRequestDeletion:
    async def test_immediate_deletion_no_workspaces(
        self,
        session: AsyncSession,
        user: User,
    ) -> None:
        """User with no workspaces is immediately deleted."""
        original_email = user.email

        result = await user_service.request_deletion(session, user)

        assert result.deleted is True
        assert result.blocked_reasons == []
        assert user.deleted_at is not None
        assert user.email != original_email
        assert user.email.endswith("@redacted.invalid")

    async def test_blocked_with_active_workspace(
        self,
        session: AsyncSession,
        user: User,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """User with active workspace is blocked from deletion."""
        result = await user_service.request_deletion(session, user)

        assert result.deleted is False
        assert UserDeletionBlockedReason.HAS_ACTIVE_WORKSPACES in result.blocked_reasons
        assert len(result.blocking_workspaces) == 1
        assert user.deleted_at is None

    async def test_anonymization(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        user: User,
    ) -> None:
        """User PII is properly anonymized on deletion."""
        user.avatar_url = "https://example.com/avatar.png"
        user.meta = {"signup": {"intent": "creator"}}
        await save_fixture(user)

        original_email = user.email

        result = await user_service.request_deletion(session, user)

        assert result.deleted is True
        assert user.email != original_email
        assert user.email.endswith("@redacted.invalid")
        assert user.avatar_url is None
        assert user.meta == {}
        assert user.deleted_at is not None

    async def test_oauth_accounts_deleted(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        user: User,
    ) -> None:
        """OAuth accounts are deleted when user is deleted."""
        await create_oauth_account(save_fixture, user, OAuthPlatform.microsoft)
        await create_oauth_account(save_fixture, user, OAuthPlatform.google)

        stmt = select(OAuthAccount).where(OAuthAccount.user_id == user.id)
        result = await session.execute(stmt)
        assert len(result.scalars().all()) == 2

        deletion_result = await user_service.request_deletion(session, user)

        assert deletion_result.deleted is True

        result = await session.execute(stmt)
        assert len(result.scalars().all()) == 0

    async def test_notification_recipients_deleted(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        user: User,
    ) -> None:
        """Notification recipients are soft-deleted when user is deleted."""
        await create_notification_recipient(
            save_fixture, user=user, expo_push_token="ExponentPushToken[token1]"
        )
        await create_notification_recipient(
            save_fixture, user=user, expo_push_token="ExponentPushToken[token2]"
        )

        stmt = select(NotificationRecipient).where(
            NotificationRecipient.user_id == user.id,
            NotificationRecipient.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        assert len(result.scalars().all()) == 2

        deletion_result = await user_service.request_deletion(session, user)

        assert deletion_result.deleted is True

        result = await session.execute(stmt)
        assert len(result.scalars().all()) == 0

        stmt_all = select(NotificationRecipient).where(
            NotificationRecipient.user_id == user.id,
        )
        result = await session.execute(stmt_all)
        recipients = result.scalars().all()
        assert len(recipients) == 2
        assert all(r.deleted_at is not None for r in recipients)
