"""Tests for customer portal customer session endpoints."""

import uuid
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from pytest_mock import MockerFixture

from rapidly.models import Member, Workspace
from rapidly.models.member import MemberRole
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_customer

# ── Fixtures ──


@pytest.fixture(autouse=True)
def mock_send_email(mocker: MockerFixture) -> MagicMock:
    """Mock the customer session service send method to prevent actual email sending."""
    return mocker.patch(
        "rapidly.customers.customer_portal.api.customer_session.customer_session_service.send",
        autospec=True,
    )


# ── Request Session ──


@pytest.mark.asyncio
class TestRequest:
    async def test_invalid_workspace_returns_202(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that invalid workspace returns 202 (no information leak)."""
        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": "test@example.com",
                "workspace_id": str(uuid.uuid4()),
            },
        )
        # Returns 202 to prevent workspace enumeration
        assert response.status_code == 202


# ── Request Session for Legacy Org ──


@pytest.mark.asyncio
class TestRequestLegacyOrg:
    """Tests for orgs with member_model_enabled=false (legacy customer lookup)."""

    async def test_customer_exists_returns_202(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that existing customer returns 202 (legacy path)."""
        # workspace defaults to member_model_enabled=false
        await create_customer(
            save_fixture, workspace=workspace, email="test@example.com"
        )

        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": "test@example.com",
                "workspace_id": str(workspace.id),
            },
        )
        assert response.status_code == 202

    async def test_customer_does_not_exist_returns_202(
        self,
        client: AsyncClient,
        workspace: Workspace,
    ) -> None:
        """Test that non-existent email returns 202 (no information leak, legacy path)."""
        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": "nonexistent@example.com",
                "workspace_id": str(workspace.id),
            },
        )
        # Returns 202 to prevent email enumeration
        assert response.status_code == 202

    async def test_case_insensitive_email(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that email matching is case-insensitive (legacy path)."""
        await create_customer(
            save_fixture, workspace=workspace, email="user@example.com"
        )

        # Test uppercase
        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": "USER@EXAMPLE.COM",
                "workspace_id": str(workspace.id),
            },
        )
        assert response.status_code == 202


# ── Request Session for Member-Enabled Org ──


@pytest.mark.asyncio
class TestRequestMemberEnabledOrg:
    """Tests for orgs with member_model_enabled=true (member-based lookup)."""

    async def test_no_members_returns_202(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that non-existent email returns 202 (no information leak)."""
        workspace.feature_settings = {"member_model_enabled": True}
        await save_fixture(workspace)

        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": "nonexistent@example.com",
                "workspace_id": str(workspace.id),
            },
        )
        # Returns 202 to prevent email enumeration
        assert response.status_code == 202

    async def test_single_member_returns_202(
        self,
        client: AsyncClient,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that single member match returns 202 and sends code."""
        workspace.feature_settings = {"member_model_enabled": True}
        await save_fixture(workspace)

        customer = await create_customer(
            save_fixture, workspace=workspace, email="test@example.com"
        )
        member = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="test@example.com",
            name="Test User",
            role=MemberRole.owner,
        )
        await save_fixture(member)

        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": "test@example.com",
                "workspace_id": str(workspace.id),
            },
        )
        assert response.status_code == 202

    async def test_multiple_members_returns_409_with_customer_list(
        self,
        client: AsyncClient,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that multiple member match returns 409 with customer selection."""
        workspace.feature_settings = {"member_model_enabled": True}
        await save_fixture(workspace)

        customer1 = await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer1@example.com",
            name="Customer One",
        )
        customer2 = await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer2@example.com",
            name="Customer Two",
        )

        shared_email = "shared@example.com"
        member1 = Member(
            customer_id=customer1.id,
            workspace_id=workspace.id,
            email=shared_email,
            name="Member One",
            role=MemberRole.owner,
        )
        member2 = Member(
            customer_id=customer2.id,
            workspace_id=workspace.id,
            email=shared_email,
            name="Member Two",
            role=MemberRole.owner,
        )
        await save_fixture(member1)
        await save_fixture(member2)

        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": shared_email,
                "workspace_id": str(workspace.id),
            },
        )

        assert response.status_code == 409
        data = response.json()
        assert data["error"] == "customer_selection_required"
        assert (
            data["detail"]
            == "Multiple customers found for this email. Please select one."
        )
        assert len(data["customers"]) == 2

        # Verify customer info
        customer_ids = {c["id"] for c in data["customers"]}
        assert str(customer1.id) in customer_ids
        assert str(customer2.id) in customer_ids

        customer_names = {c["name"] for c in data["customers"]}
        assert "Customer One" in customer_names
        assert "Customer Two" in customer_names

    async def test_multiple_members_with_valid_customer_id_returns_202(
        self,
        client: AsyncClient,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that selecting a customer from multiple returns 202."""
        workspace.feature_settings = {"member_model_enabled": True}
        await save_fixture(workspace)

        customer1 = await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer1@example.com",
            name="Customer One",
        )
        customer2 = await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer2@example.com",
            name="Customer Two",
        )

        shared_email = "shared@example.com"
        member1 = Member(
            customer_id=customer1.id,
            workspace_id=workspace.id,
            email=shared_email,
            role=MemberRole.owner,
        )
        member2 = Member(
            customer_id=customer2.id,
            workspace_id=workspace.id,
            email=shared_email,
            role=MemberRole.owner,
        )
        await save_fixture(member1)
        await save_fixture(member2)

        # Select customer1
        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": shared_email,
                "workspace_id": str(workspace.id),
                "customer_id": str(customer1.id),
            },
        )
        assert response.status_code == 202

        # Select customer2
        response2 = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": shared_email,
                "workspace_id": str(workspace.id),
                "customer_id": str(customer2.id),
            },
        )
        assert response2.status_code == 202

    async def test_multiple_members_with_invalid_customer_id_returns_202(
        self,
        client: AsyncClient,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that invalid customer_id returns 202 (no information leak)."""
        workspace.feature_settings = {"member_model_enabled": True}
        await save_fixture(workspace)

        customer1 = await create_customer(
            save_fixture, workspace=workspace, email="customer1@example.com"
        )
        customer2 = await create_customer(
            save_fixture, workspace=workspace, email="customer2@example.com"
        )

        shared_email = "shared@example.com"
        member1 = Member(
            customer_id=customer1.id,
            workspace_id=workspace.id,
            email=shared_email,
            role=MemberRole.owner,
        )
        member2 = Member(
            customer_id=customer2.id,
            workspace_id=workspace.id,
            email=shared_email,
            role=MemberRole.owner,
        )
        await save_fixture(member1)
        await save_fixture(member2)

        # Use invalid customer_id
        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": shared_email,
                "workspace_id": str(workspace.id),
                "customer_id": str(uuid.uuid4()),
            },
        )
        # Returns 202 to prevent customer_id enumeration
        assert response.status_code == 202

    async def test_case_insensitive_email(
        self,
        client: AsyncClient,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test that email matching is case-insensitive."""
        workspace.feature_settings = {"member_model_enabled": True}
        await save_fixture(workspace)

        customer = await create_customer(
            save_fixture, workspace=workspace, email="user@example.com"
        )
        member = Member(
            customer_id=customer.id,
            workspace_id=workspace.id,
            email="user@example.com",
            role=MemberRole.owner,
        )
        await save_fixture(member)

        # Test uppercase
        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": "USER@EXAMPLE.COM",
                "workspace_id": str(workspace.id),
            },
        )
        assert response.status_code == 202

        # Test mixed case
        response2 = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": "User@Example.Com",
                "workspace_id": str(workspace.id),
            },
        )
        assert response2.status_code == 202

    async def test_customer_with_null_name(
        self,
        client: AsyncClient,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Test 409 response includes customers with null names."""
        workspace.feature_settings = {"member_model_enabled": True}
        await save_fixture(workspace)

        customer1 = await create_customer(
            save_fixture, workspace=workspace, email="customer1@example.com"
        )
        # Set name to None
        customer1.name = None
        await save_fixture(customer1)

        customer2 = await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer2@example.com",
            name="Has Name",
        )

        shared_email = "shared@example.com"
        member1 = Member(
            customer_id=customer1.id,
            workspace_id=workspace.id,
            email=shared_email,
            role=MemberRole.owner,
        )
        member2 = Member(
            customer_id=customer2.id,
            workspace_id=workspace.id,
            email=shared_email,
            role=MemberRole.owner,
        )
        await save_fixture(member1)
        await save_fixture(member2)

        response = await client.post(
            "/api/customer-portal/customer-session/request",
            json={
                "email": shared_email,
                "workspace_id": str(workspace.id),
            },
        )

        assert response.status_code == 409
        data = response.json()
        assert len(data["customers"]) == 2

        # Verify one has null name
        names = [c["name"] for c in data["customers"]]
        assert None in names
        assert "Has Name" in names
