"""Tests for workspace endpoints."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from pytest_mock import MockerFixture

from rapidly.enums import AccountType
from rapidly.models import Share, User
from rapidly.models.account import Account
from rapidly.models.user import IdentityVerificationStatus
from rapidly.models.workspace import Workspace, WorkspaceStatus
from rapidly.models.workspace_membership import WorkspaceMembership
from rapidly.platform.workspace_membership import (
    actions as workspace_membership_service,
)
from rapidly.postgres import AsyncSession
from tests.fixtures.auth import AuthSubjectFixture
from tests.fixtures.database import SaveFixture

# ── List Workspaces ──


@pytest.mark.asyncio
class TestListWorkspaces:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.get("/api/workspaces/")

        assert response.status_code == 401

    @pytest.mark.auth
    async def test_not_member(self, client: AsyncClient) -> None:
        response = await client.get("/api/workspaces/")

        assert response.status_code == 200

        json = response.json()
        assert json["meta"]["total"] == 0

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_valid(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get("/api/workspaces/")

        assert response.status_code == 200

        json = response.json()
        assert json["meta"]["total"] == 1
        assert json["data"][0]["id"] == str(workspace.id)


# ── Get Workspace ──


@pytest.mark.asyncio
class TestGetWorkspace:
    async def test_anonymous(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.get(f"/api/workspaces/{workspace.id}")

        assert response.status_code == 401

    @pytest.mark.auth
    async def test_not_member(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.get(f"/api/workspaces/{workspace.id}")

        assert response.status_code == 404

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_not_existing(self, client: AsyncClient) -> None:
        response = await client.get(f"/api/workspaces/{uuid.uuid4()}")

        assert response.status_code == 404

    @pytest.mark.auth(
        AuthSubjectFixture(subject="user"),
        AuthSubjectFixture(subject="workspace"),
    )
    async def test_valid(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get(f"/api/workspaces/{workspace.id}")

        assert response.status_code == 200

        json = response.json()
        assert json["id"] == str(workspace.id)


# ── Update Workspace ──


@pytest.mark.asyncio
class TestUpdateWorkspace:
    @pytest.mark.auth
    async def test_not_existing(self, client: AsyncClient) -> None:
        response = await client.patch(f"/api/workspaces/{uuid.uuid4()}", json={})

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_not_admin(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.patch(f"/api/workspaces/{workspace.id}", json={})

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_valid_user(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.patch(
            f"/api/workspaces/{workspace.id}", json={"name": "Updated"}
        )

        assert response.status_code == 200

        json = response.json()
        assert json["name"] == "Updated"

    @pytest.mark.auth
    async def test_negative_revenue_validation(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        # Test negative future_annual_revenue
        response = await client.patch(
            f"/api/workspaces/{workspace.id}",
            json={
                "details": {
                    "about": "Test company",
                    "product_description": "SaaS share",
                    "intended_use": "API integration",
                    "customer_acquisition": ["website"],
                    "future_annual_revenue": -1000,
                    "switching": False,
                    "previous_annual_revenue": 25000,
                }
            },
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("future_annual_revenue" in str(error) for error in error_detail)

    @pytest.mark.auth
    async def test_negative_previous_revenue_validation(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        # Test negative previous_annual_revenue
        response = await client.patch(
            f"/api/workspaces/{workspace.id}",
            json={
                "details": {
                    "about": "Test company",
                    "product_description": "SaaS share",
                    "intended_use": "API integration",
                    "customer_acquisition": ["website"],
                    "future_annual_revenue": 50000,
                    "switching": False,
                    "previous_annual_revenue": -5000,
                }
            },
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("previous_annual_revenue" in str(error) for error in error_detail)

    @pytest.mark.auth
    async def test_enable_tinybird_read_with_member_model(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        workspace.feature_settings = {
            "member_model_enabled": True,
            "tinybird_read": False,
        }
        await save_fixture(workspace)

        response = await client.patch(
            f"/api/workspaces/{workspace.id}",
            json={
                "feature_settings": {
                    "tinybird_read": True,
                },
            },
        )

        assert response.status_code == 200
        assert response.json()["feature_settings"]["tinybird_read"] is True

    @pytest.mark.auth
    async def test_enable_tinybird_compare(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        workspace.feature_settings = {
            "member_model_enabled": False,
            "tinybird_compare": False,
        }
        await save_fixture(workspace)

        response = await client.patch(
            f"/api/workspaces/{workspace.id}",
            json={
                "feature_settings": {
                    "tinybird_compare": True,
                },
            },
        )

        assert response.status_code == 200
        assert response.json()["feature_settings"]["tinybird_compare"] is True

    @pytest.mark.auth
    async def test_disable_tinybird_read_when_enabled(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        workspace.feature_settings = {
            "member_model_enabled": True,
            "tinybird_read": True,
        }
        await save_fixture(workspace)

        response = await client.patch(
            f"/api/workspaces/{workspace.id}",
            json={
                "feature_settings": {
                    "tinybird_read": False,
                },
            },
        )

        assert response.status_code == 200
        assert response.json()["feature_settings"]["tinybird_read"] is False


# ── Invite Workspace Members ──


@pytest.mark.asyncio
class TestInviteWorkspace:
    @pytest.mark.auth
    async def test_not_existing(self, client: AsyncClient) -> None:
        response = await client.patch(f"/api/workspaces/{uuid.uuid4()}", json={})

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_inviter_not_part_of_org(
        self,
        client: AsyncClient,
        session: AsyncSession,
        workspace: Workspace,
        # workspace_membership: WorkspaceMembership,
    ) -> None:
        members_before = await workspace_membership_service.list_by_org(
            session, workspace.id
        )
        response = await client.post(
            f"/api/workspaces/{workspace.id}/members/invite",
            json={"email": "test@rapidly.tech"},
        )
        assert response.status_code == 404

        members_after = await workspace_membership_service.list_by_org(
            session, workspace.id
        )

        assert set(members_after) == set(members_before)

    @pytest.mark.auth
    @pytest.mark.keep_session_state
    async def test_inviter_part_of_org(
        self,
        client: AsyncClient,
        session: AsyncSession,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,  # Makes this user part of the workspace
    ) -> None:
        email_to_invite = "test@rapidly.tech"

        members_before = await workspace_membership_service.list_by_org(
            session, workspace.id
        )
        response = await client.post(
            f"/api/workspaces/{workspace.id}/members/invite",
            json={"email": email_to_invite},
        )
        assert response.status_code == 201
        json = response.json()
        assert json["email"] == email_to_invite

        members_after = await workspace_membership_service.list_by_org(
            session, workspace.id
        )

        new_members = set(members_after) - set(members_before)
        assert len(new_members) == 1
        assert list(new_members)[0].user.email == email_to_invite

    @pytest.mark.auth
    @pytest.mark.keep_session_state
    async def test_already_invited(
        self,
        client: AsyncClient,
        session: AsyncSession,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        workspace_membership_second: WorkspaceMembership,  # second user part of this org
    ) -> None:
        email_already_in_org = workspace_membership_second.user.email

        members_before = await workspace_membership_service.list_by_org(
            session, workspace.id
        )
        assert len(members_before) == 2

        response = await client.post(
            f"/api/workspaces/{workspace.id}/members/invite",
            json={"email": email_already_in_org},
        )
        assert response.status_code == 200
        json = response.json()
        assert json["email"] == email_already_in_org

        members_after = await workspace_membership_service.list_by_org(
            session, workspace.id
        )

        assert set(members_after) == set(members_before)
        assert len(members_after) == 2


# ── List Members ──


@pytest.mark.asyncio
@pytest.mark.auth
async def test_list_members(
    session: AsyncSession,
    workspace: Workspace,
    workspace_membership: WorkspaceMembership,  # makes User a member of Workspace
    workspace_membership_second: WorkspaceMembership,  # adds another member
    client: AsyncClient,
) -> None:
    response = await client.get(f"/api/workspaces/{workspace.id}/members")

    assert response.status_code == 200

    json = response.json()
    assert len(json["data"]) == 2


@pytest.mark.asyncio
@pytest.mark.auth
async def test_list_members_not_member(
    session: AsyncSession,
    workspace: Workspace,
    # workspace_membership: WorkspaceMembership,  # makes User a member of Workspace
    workspace_membership_second: WorkspaceMembership,  # adds another member
    client: AsyncClient,
) -> None:
    response = await client.get(f"/api/workspaces/{workspace.id}/members")

    assert response.status_code == 404


# ── Get Payment Status ──


@pytest.mark.asyncio
class TestGetPaymentStatus:
    async def test_anonymous(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.get(f"/api/workspaces/{workspace.id}/payment-status")
        assert response.status_code == 401

    async def test_anonymous_with_account_verification_only(
        self,
        client: AsyncClient,
        workspace: Workspace,
        save_fixture: SaveFixture,
    ) -> None:
        # Make this a new workspace (not grandfathered)
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        await save_fixture(workspace)

        response = await client.get(
            f"/api/workspaces/{workspace.id}/payment-status?account_verification_only=true"
        )
        assert response.status_code == 200

        json = response.json()
        # When account_verification_only=true, we should get minimal response
        # focusing only on account setup (no share/integration steps)
        assert "payment_ready" in json
        assert "steps" in json
        assert "workspace_status" in json

        # With account_verification_only=true, only account setup step should be present
        step_ids = [step["id"] for step in json["steps"]]
        assert "setup_account" in step_ids
        assert len(step_ids) == 1
        assert json["payment_ready"] is False

    @pytest.mark.auth
    async def test_not_member(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.get(f"/api/workspaces/{workspace.id}/payment-status")
        assert response.status_code == 404

    @pytest.mark.auth
    async def test_valid_no_steps_complete(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        # Make this a new workspace (not grandfathered)
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        await save_fixture(workspace)

        response = await client.get(f"/api/workspaces/{workspace.id}/payment-status")
        assert response.status_code == 200

        json = response.json()
        assert json["payment_ready"] is False
        assert len(json["steps"]) == 3

        # All steps should be incomplete
        for step in json["steps"]:
            assert step["completed"] is False

        # Check specific steps exist
        step_ids = [step["id"] for step in json["steps"]]
        assert "create_product" in step_ids
        assert "integrate_api" in step_ids
        assert "setup_account" in step_ids

    @pytest.mark.auth
    async def test_valid_with_product(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        share: Share,
    ) -> None:
        # Make this a new workspace (not grandfathered)
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        await save_fixture(workspace)

        response = await client.get(f"/api/workspaces/{workspace.id}/payment-status")
        assert response.status_code == 200

        json = response.json()
        assert json["payment_ready"] is False

        # Share step should be complete
        product_step = next(s for s in json["steps"] if s["id"] == "create_product")
        assert product_step["completed"] is True

    @pytest.mark.auth
    async def test_valid_with_api_key(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        mocker: MockerFixture,
    ) -> None:
        # Make this a new workspace (not grandfathered)
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        await save_fixture(workspace)

        # Mock the API key count
        mocker.patch(
            "rapidly.platform.workspace_access_token.queries.WorkspaceAccessTokenRepository.count_by_workspace_id",
            return_value=1,  # Has 1 API key
        )

        response = await client.get(f"/api/workspaces/{workspace.id}/payment-status")
        assert response.status_code == 200

        json = response.json()
        assert json["payment_ready"] is False

        # API integration step should be complete
        api_step = next(s for s in json["steps"] if s["id"] == "integrate_api")
        assert api_step["completed"] is True

    @pytest.mark.auth
    async def test_valid_grandfathered_workspace(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        # Make workspace grandfathered
        workspace.created_at = datetime(2025, 8, 4, 8, 0, tzinfo=UTC)
        await save_fixture(workspace)

        response = await client.get(f"/api/workspaces/{workspace.id}/payment-status")
        assert response.status_code == 200

        json = response.json()
        # Should be payment ready even without completing steps
        assert json["payment_ready"] is True

    @pytest.mark.auth
    async def test_valid_all_steps_complete(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        share: Share,
        mocker: MockerFixture,
        user: User,
    ) -> None:
        # Set up as new workspace
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        workspace.status = WorkspaceStatus.ACTIVE
        workspace.details_submitted_at = datetime.now(UTC)
        workspace.details = {"about": "Test"}  # type: ignore

        # Set up user verification
        user.identity_verification_status = IdentityVerificationStatus.verified
        await save_fixture(user)

        # Set up account (only checking is_details_submitted now)
        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=False,  # Can be false
            is_payouts_enabled=False,  # Can be false
            stripe_id="STRIPE_ACCOUNT_ID",
        )
        await save_fixture(account)

        workspace.account = account
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Mock the API key count
        mocker.patch(
            "rapidly.platform.workspace_access_token.queries.WorkspaceAccessTokenRepository.count_by_workspace_id",
            return_value=1,  # Has 1 API key
        )

        response = await client.get(f"/api/workspaces/{workspace.id}/payment-status")
        assert response.status_code == 200

        json = response.json()
        assert json["payment_ready"] is True

        # All steps should be complete
        for step in json["steps"]:
            assert step["completed"] is True


# ── Get Account ──


@pytest.mark.asyncio
class TestGetAccount:
    async def test_anonymous(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.get(f"/api/workspaces/{workspace.id}/account")

        assert response.status_code == 401

    @pytest.mark.auth
    async def test_not_member(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.get(f"/api/workspaces/{workspace.id}/account")

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_workspace_not_found(self, client: AsyncClient) -> None:
        response = await client.get(f"/api/workspaces/{uuid.uuid4()}/account")

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_no_account_set(
        self,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        save_fixture: SaveFixture,
    ) -> None:
        workspace.account_id = None
        await save_fixture(workspace)

        response = await client.get(f"/api/workspaces/{workspace.id}/account")

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_not_account_admin(
        self,
        client: AsyncClient,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        user: User,
    ) -> None:
        # Create an account with a different admin (not the current user)
        other_user = User(
            email="other@example.com",
        )
        await save_fixture(other_user)

        account = Account(
            account_type=AccountType.stripe,
            admin_id=other_user.id,  # Different admin than the current user
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
        )
        await save_fixture(account)

        # Link account to workspace
        workspace.account_id = account.id
        await save_fixture(workspace)

        response = await client.get(f"/api/workspaces/{workspace.id}/account")

        assert response.status_code == 403
        json = response.json()
        assert json["detail"] == "You are not the admin of this account"

    @pytest.mark.auth
    async def test_valid_account_admin(
        self,
        client: AsyncClient,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        user: User,
    ) -> None:
        # Create an account with the current user as admin
        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,  # Current user is the admin
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
        )
        await save_fixture(account)

        # Link account to workspace
        workspace.account_id = account.id
        await save_fixture(workspace)

        response = await client.get(f"/api/workspaces/{workspace.id}/account")

        assert response.status_code == 200
        json = response.json()
        assert json["id"] == str(account.id)
        assert json["account_type"] == "stripe"
        assert json["country"] == "US"
        assert json["is_details_submitted"]
        assert json["is_charges_enabled"]
        assert json["is_payouts_enabled"]


# ── Delete Workspace ──


@pytest.mark.asyncio
class TestDeleteWorkspace:
    async def test_anonymous(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.delete(f"/api/workspaces/{workspace.id}")
        assert response.status_code == 401

    @pytest.mark.auth
    async def test_not_member(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.delete(f"/api/workspaces/{workspace.id}")
        assert response.status_code == 404

    @pytest.mark.auth
    async def test_not_existing(self, client: AsyncClient) -> None:
        response = await client.delete(f"/api/workspaces/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.auth
    async def test_valid_no_activity(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        mocker: MockerFixture,
    ) -> None:
        # Mock the dispatch_task to prevent actual task execution
        mock_enqueue = mocker.patch("rapidly.platform.workspace.actions.dispatch_task")

        response = await client.delete(f"/api/workspaces/{workspace.id}")

        assert response.status_code == 200
        json = response.json()
        assert json["deleted"] is True
        assert json["requires_support"] is False
        assert json["blocked_reasons"] == []

        # Ensure no background task was enqueued (immediate deletion)
        mock_enqueue.assert_not_called()

    @pytest.mark.auth
    async def test_valid_with_account_deletion(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        user: User,
        mocker: MockerFixture,
    ) -> None:
        # Create an account for the workspace
        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="acct_test123",
        )
        await save_fixture(account)
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Mock Stripe account deletion to succeed (returns None on success)
        mock_stripe_delete = mocker.patch(
            "rapidly.billing.account.actions.delete_stripe_account",
            return_value=None,
        )
        mock_enqueue = mocker.patch("rapidly.platform.workspace.actions.dispatch_task")

        response = await client.delete(f"/api/workspaces/{workspace.id}")

        assert response.status_code == 200
        json = response.json()
        assert json["deleted"] is True
        assert json["requires_support"] is False
        assert json["blocked_reasons"] == []

        # Stripe account should have been deleted
        mock_stripe_delete.assert_called_once()
        # No background task should be enqueued (immediate deletion)
        mock_enqueue.assert_not_called()

    @pytest.mark.auth
    async def test_stripe_account_deletion_failure(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        user: User,
        mocker: MockerFixture,
    ) -> None:
        # Create an account for the workspace
        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="acct_test123",
        )
        await save_fixture(account)
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Mock Stripe account deletion to fail with an exception
        from rapidly.billing.account.actions import AccountServiceError

        mock_stripe_delete = mocker.patch(
            "rapidly.billing.account.actions.delete_stripe_account",
            side_effect=AccountServiceError("Stripe account deletion failed"),
        )
        mock_enqueue = mocker.patch("rapidly.platform.workspace.actions.dispatch_task")

        response = await client.delete(f"/api/workspaces/{workspace.id}")

        assert response.status_code == 200
        json = response.json()
        assert json["deleted"] is False
        assert json["requires_support"] is True
        assert "stripe_account_deletion_failed" in json["blocked_reasons"]

        # Stripe account deletion should have been attempted
        mock_stripe_delete.assert_called_once()
        # Background task should be enqueued for support ticket
        mock_enqueue.assert_called_once()

    @pytest.mark.auth
    async def test_not_admin_with_account(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        user: User,
        mocker: MockerFixture,
    ) -> None:
        # Create an account with a different admin (not the current user)
        other_user = User(
            email="other@example.com",
        )
        await save_fixture(other_user)

        account = Account(
            account_type=AccountType.stripe,
            admin_id=other_user.id,  # Different admin than the current user
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="acct_test123",
        )
        await save_fixture(account)
        workspace.account_id = account.id
        await save_fixture(workspace)

        response = await client.delete(f"/api/workspaces/{workspace.id}")

        assert response.status_code == 403
        json = response.json()
        assert (
            json["detail"]
            == "Only the account admin can delete an workspace with an account"
        )
