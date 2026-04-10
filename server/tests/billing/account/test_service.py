"""Tests for account service."""

import pytest

from rapidly.billing.account import actions as account_service
from rapidly.billing.account.actions import (
    CannotChangeAdminError,
    UserNotWorkspaceMemberError,
)
from rapidly.core.pagination import PaginationParams
from rapidly.core.utils import now_utc
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import Account, User, Workspace, WorkspaceMembership
from rapidly.models.user import IdentityVerificationStatus
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture

from .conftest import create_account

# ── Helpers ──


async def create_workspace_membership(
    save_fixture: SaveFixture, *, user: User, workspace: Workspace
) -> WorkspaceMembership:
    workspace_membership = WorkspaceMembership(
        user_id=user.id,
        workspace_id=workspace.id,
    )
    await save_fixture(workspace_membership)
    return workspace_membership


# ── Change Admin ──


@pytest.mark.asyncio
class TestChangeAdmin:
    async def test_change_admin_success_verified_user(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
        user_second: User,
    ) -> None:
        # Set up verified user
        user_second.identity_verification_status = IdentityVerificationStatus.verified
        await save_fixture(user_second)

        # Create user-workspace relationships
        await create_workspace_membership(save_fixture, user=user, workspace=workspace)
        await create_workspace_membership(
            save_fixture, user=user_second, workspace=workspace
        )

        # Create account with current admin (no Stripe ID)
        account = await create_account(
            save_fixture, admin=user, status=Account.Status.ACTIVE
        )
        account.stripe_id = None
        await save_fixture(account)

        # Test successful admin change
        updated_account = await account_service.change_admin(
            session, account, user_second.id, workspace.id
        )

        assert updated_account.admin_id == user_second.id
        assert updated_account.id == account.id

    async def test_change_admin_fails_stripe_account_exists(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
        user_second: User,
    ) -> None:
        # Set up verified user
        user_second.identity_verification_status = IdentityVerificationStatus.verified
        await save_fixture(user_second)

        # Create user-workspace relationships
        await create_workspace_membership(save_fixture, user=user, workspace=workspace)
        await create_workspace_membership(
            save_fixture, user=user_second, workspace=workspace
        )

        # Create account with Stripe ID
        account = await create_account(
            save_fixture, admin=user, status=Account.Status.ACTIVE
        )
        account.stripe_id = "acct_123456789"
        await save_fixture(account)

        # Test that admin change fails due to Stripe account
        with pytest.raises(
            CannotChangeAdminError, match="Stripe account must be deleted"
        ):
            await account_service.change_admin(
                session, account, user_second.id, workspace.id
            )

    @pytest.mark.parametrize(
        ("verification_status", "expected_status_name"),
        [
            (IdentityVerificationStatus.unverified, "Unverified"),
            (IdentityVerificationStatus.pending, "Pending"),
            (IdentityVerificationStatus.failed, "Failed"),
        ],
    )
    async def test_change_admin_fails_user_not_verified(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
        user_second: User,
        verification_status: IdentityVerificationStatus,
        expected_status_name: str,
    ) -> None:
        # Set up user with non-verified status
        user_second.identity_verification_status = verification_status
        await save_fixture(user_second)

        # Create user-workspace relationships
        await create_workspace_membership(save_fixture, user=user, workspace=workspace)
        await create_workspace_membership(
            save_fixture, user=user_second, workspace=workspace
        )

        # Create account without Stripe ID
        account = await create_account(
            save_fixture, admin=user, status=Account.Status.ACTIVE
        )
        account.stripe_id = None
        await save_fixture(account)

        # Test that admin change fails due to non-verified user
        with pytest.raises(
            CannotChangeAdminError,
            match=f"New admin must be verified.*{expected_status_name}",
        ):
            await account_service.change_admin(
                session, account, user_second.id, workspace.id
            )

    async def test_change_admin_fails_user_not_workspace_member(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
        user_second: User,
    ) -> None:
        # Set up verified user but don't add to workspace
        user_second.identity_verification_status = IdentityVerificationStatus.verified
        await save_fixture(user_second)

        # Create user-workspace relationship only for current admin
        await create_workspace_membership(save_fixture, user=user, workspace=workspace)

        # Create account
        account = await create_account(
            save_fixture, admin=user, status=Account.Status.ACTIVE
        )
        account.stripe_id = None
        await save_fixture(account)

        # Test that admin change fails for non-member
        with pytest.raises(UserNotWorkspaceMemberError):
            await account_service.change_admin(
                session, account, user_second.id, workspace.id
            )

    async def test_change_admin_fails_same_admin(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
    ) -> None:
        # Set up verified user
        user.identity_verification_status = IdentityVerificationStatus.verified
        await save_fixture(user)

        # Create user-workspace relationship
        await create_workspace_membership(save_fixture, user=user, workspace=workspace)

        # Create account
        account = await create_account(
            save_fixture, admin=user, status=Account.Status.ACTIVE
        )
        account.stripe_id = None
        await save_fixture(account)

        # Test that admin change fails when trying to set same admin
        with pytest.raises(
            CannotChangeAdminError, match="New admin is the same as current admin"
        ):
            await account_service.change_admin(session, account, user.id, workspace.id)


# ── Search ──


@pytest.mark.asyncio
class TestSearch:
    async def test_search_filters_deleted_workspaces(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        user: User,
        workspace: Workspace,
    ) -> None:
        # Create account with user as admin
        account = await create_account(
            save_fixture, admin=user, status=Account.Status.ACTIVE
        )

        # Associate the existing workspace with the account
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Create a second workspace that will be marked as deleted
        workspace_deleted = Workspace(
            name="Deleted Workspace",
            slug="deleted-org",
            account_id=account.id,
            customer_invoice_prefix="DEL",
            deleted_at=now_utc(),  # Mark as deleted
        )
        await save_fixture(workspace_deleted)

        # Create auth subject
        auth_subject = AuthPrincipal[User](subject=user, scopes=set(), session=None)

        # Search for accounts
        accounts, count = await account_service.search(
            session, auth_subject, pagination=PaginationParams(limit=10, page=1)
        )

        # Verify results
        assert count == 1
        assert len(accounts) == 1
        assert accounts[0].id == account.id

        # Verify only active workspace is included
        assert len(accounts[0].workspaces) == 1
        assert accounts[0].workspaces[0].id == workspace.id
        assert accounts[0].workspaces[0].slug == workspace.slug

    async def test_search_includes_all_active_workspaces(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        user: User,
        workspace: Workspace,
    ) -> None:
        # Create account with user as admin
        account = await create_account(
            save_fixture, admin=user, status=Account.Status.ACTIVE
        )

        # Associate the existing workspace with the account
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Create a second active workspace
        workspace_two = Workspace(
            name="Workspace Two",
            slug="org-two",
            account_id=account.id,
            customer_invoice_prefix="ORG2",
        )
        await save_fixture(workspace_two)

        # Create auth subject
        auth_subject = AuthPrincipal[User](subject=user, scopes=set(), session=None)

        # Search for accounts
        accounts, count = await account_service.search(
            session, auth_subject, pagination=PaginationParams(limit=10, page=1)
        )

        # Verify both active workspaces are included
        assert count == 1
        assert len(accounts) == 1
        assert len(accounts[0].workspaces) == 2

        # Verify workspace slugs
        workspace_slugs = {org.slug for org in accounts[0].workspaces}
        assert workspace_slugs == {workspace.slug, "org-two"}


# ── Get ──


@pytest.mark.asyncio
class TestGet:
    async def test_get_filters_deleted_workspaces(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        user: User,
        workspace: Workspace,
    ) -> None:
        # Create account with user as admin
        account = await create_account(
            save_fixture, admin=user, status=Account.Status.ACTIVE
        )

        # Associate the existing workspace with the account
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Create a deleted workspace
        workspace_deleted = Workspace(
            name="Deleted Workspace",
            slug="deleted-org",
            account_id=account.id,
            customer_invoice_prefix="DEL",
            deleted_at=now_utc(),  # Mark as deleted
        )
        await save_fixture(workspace_deleted)

        # Create auth subject
        auth_subject = AuthPrincipal[User](subject=user, scopes=set(), session=None)

        # Get the account
        retrieved_account = await account_service.get(session, auth_subject, account.id)

        # Verify account was retrieved
        assert retrieved_account is not None
        assert retrieved_account.id == account.id

        # Verify only active workspace is included
        assert len(retrieved_account.workspaces) == 1
        assert retrieved_account.workspaces[0].id == workspace.id
        assert retrieved_account.workspaces[0].slug == workspace.slug

    async def test_get_returns_none_for_nonexistent_account(
        self,
        session: AsyncSession,
        user: User,
    ) -> None:
        # Create auth subject
        auth_subject = AuthPrincipal[User](subject=user, scopes=set(), session=None)

        # Try to get non-existent account
        retrieved_account = await account_service.get(
            session,
            auth_subject,
            user.id,  # Using user.id as fake account ID
        )

        # Verify no account is returned
        assert retrieved_account is None
