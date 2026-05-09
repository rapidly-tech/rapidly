"""Tests for customer endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from rapidly.identity.member.queries import MemberRepository
from rapidly.models import (
    Customer,
    Workspace,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncSession
from tests.fixtures.auth import AuthSubjectFixture
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_customer

# ── List Customers ──


@pytest.mark.asyncio
class TestListCustomers:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.get("/api/customers/")

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_missing_scope(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get("/api/customers/")

        assert response.status_code == 403

    @pytest.mark.auth
    async def test_metadata_filter(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer1@example.com",
            user_metadata={"user_id": "ABC"},
        )
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer2@example.com",
            user_metadata={"user_id": "DEF"},
        )
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer3@example.com",
            user_metadata={"user_id": "GHI"},
        )

        response = await client.get(
            "/api/customers/", params={"metadata[user_id]": ["ABC", "DEF"]}
        )

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 2

    @pytest.mark.auth
    async def test_query_filter_by_external_id(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer1@example.com",
            external_id="ext_123",
        )
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer2@example.com",
            external_id="ext_456",
        )
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer3@example.com",
            external_id="ext_789",
        )

        response = await client.get("/api/customers/", params={"query": "ext_456"})

        assert response.status_code == 200
        json = response.json()
        assert json["meta"]["total"] == 1
        assert json["data"][0]["external_id"] == "ext_456"


# ── Get Customer by External ID ──


@pytest.mark.asyncio
class TestGetExternal:
    async def test_anonymous(
        self, client: AsyncClient, customer_external_id: Customer
    ) -> None:
        response = await client.get(
            f"/api/customers/external/{customer_external_id.external_id}"
        )

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_missing_scope(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        customer_external_id: Customer,
    ) -> None:
        response = await client.get(
            f"/api/customers/external/{customer_external_id.external_id}"
        )

        assert response.status_code == 403

    @pytest.mark.auth
    async def test_not_existing(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get("/api/customers/external/not-existing")

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_valid(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        customer_external_id: Customer,
    ) -> None:
        response = await client.get(
            f"/api/customers/external/{customer_external_id.external_id}"
        )

        assert response.status_code == 200

        json = response.json()
        assert json["id"] == str(customer_external_id.id)


# ── Get Customer State ──


@pytest.mark.asyncio
class TestGetState:
    async def test_anonymous(self, client: AsyncClient, customer: Customer) -> None:
        response = await client.get(f"/api/customers/{customer.id}/state")

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_missing_scope(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        customer: Customer,
    ) -> None:
        response = await client.get(f"/api/customers/{customer.id}/state")

        assert response.status_code == 403

    @pytest.mark.auth
    async def test_not_existing(
        self, client: AsyncClient, workspace_membership: WorkspaceMembership
    ) -> None:
        response = await client.get(f"/api/customers/{uuid.uuid4()}/state")

        assert response.status_code == 404


# ── Create Customer ──


@pytest.mark.asyncio
class TestCreateCustomer:
    async def test_anonymous(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.post(
            "/api/customers/",
            json={
                "email": "customer@example.com",
                "workspace_id": str(workspace.id),
                "metadata": {"test": "test"},
            },
        )

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_missing_scope(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        workspace: Workspace,
    ) -> None:
        response = await client.post(
            "/api/customers/",
            json={
                "email": "customer@example.com",
                "workspace_id": str(workspace.id),
                "metadata": {"test": "test"},
            },
        )

        assert response.status_code == 403

    @pytest.mark.auth
    async def test_not_writable_workspace(
        self, client: AsyncClient, workspace: Workspace
    ) -> None:
        response = await client.post(
            "/api/customers/",
            json={
                "email": "customer@example.com",
                "workspace_id": str(workspace.id),
                "metadata": {"test": "test"},
            },
        )

        assert response.status_code == 422

    @pytest.mark.auth
    async def test_valid(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        workspace: Workspace,
    ) -> None:
        response = await client.post(
            "/api/customers/",
            json={
                "email": "customer@example.com",
                "workspace_id": str(workspace.id),
                "metadata": {"test": "test"},
            },
        )

        assert response.status_code == 201

        json = response.json()
        assert json["email"] == "customer@example.com"
        assert json["workspace_id"] == str(workspace.id)
        assert json["metadata"] == {"test": "test"}

    @pytest.mark.auth
    async def test_empty_external_id_converts_to_none(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        workspace: Workspace,
    ) -> None:
        # Test that empty string external_id is converted to None during creation
        response = await client.post(
            "/api/customers/",
            json={
                "email": "customer@example.com",
                "workspace_id": str(workspace.id),
                "external_id": "",
            },
        )

        assert response.status_code == 201

        json = response.json()
        assert json["email"] == "customer@example.com"
        assert json["external_id"] is None

    @pytest.mark.auth
    async def test_owner_override_all_fields(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """Test that owner email, name, and external_id can all be overridden."""
        workspace.feature_settings = {"member_model_enabled": True}
        await save_fixture(workspace)

        response = await client.post(
            "/api/customers/",
            json={
                "email": "customer@rapidly.tech",
                "name": "Customer Name",
                "external_id": "customer_ext_123",
                "workspace_id": str(workspace.id),
                "owner": {
                    "email": "owner@rapidly.tech",
                    "name": "Owner Name",
                    "external_id": "owner_ext_456",
                },
            },
        )

        assert response.status_code == 201

        json = response.json()
        assert json["email"] == "customer@rapidly.tech"
        assert json["name"] == "Customer Name"
        assert json["external_id"] == "customer_ext_123"

        member_repository = MemberRepository.from_session(session)
        owner = await member_repository.get_owner_by_customer_id(
            session, uuid.UUID(json["id"])
        )
        assert owner is not None
        assert owner.email == "owner@rapidly.tech"
        assert owner.name == "Owner Name"
        assert owner.external_id == "owner_ext_456"
        assert owner.role == "owner"


# ── Update Customer ──


@pytest.mark.asyncio
class TestUpdateCustomer:
    async def test_anonymous(self, client: AsyncClient, customer: Customer) -> None:
        response = await client.patch(
            f"/api/customers/{customer.id}",
            json={
                "metadata": {"test": "test"},
            },
        )

        assert response.status_code == 401

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_missing_scope(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        customer: Customer,
    ) -> None:
        response = await client.patch(
            f"/api/customers/{customer.id}",
            json={
                "metadata": {"test": "test"},
            },
        )

        assert response.status_code == 403

    @pytest.mark.auth
    async def test_email_already_exists(
        self,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        customer: Customer,
        customer_second: Customer,
    ) -> None:
        response = await client.patch(
            f"/api/customers/{customer.id}",
            json={
                "email": customer_second.email,
            },
        )

        assert response.status_code == 422

    @pytest.mark.auth
    async def test_email_update(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        workspace: Workspace,
    ) -> None:
        email_verified_customer = await create_customer(
            save_fixture, workspace=workspace, email_verified=True
        )
        response = await client.patch(
            f"/api/customers/{email_verified_customer.id}",
            json={"email": "email.updated@example.com"},
        )

        assert response.status_code == 200

        json = response.json()
        assert json["email"] == "email.updated@example.com"
        assert json["email_verified"] is False

    @pytest.mark.auth
    async def test_metadata_update(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        workspace: Workspace,
    ) -> None:
        email_verified_customer = await create_customer(
            save_fixture, workspace=workspace, email_verified=True
        )
        response = await client.patch(
            f"/api/customers/{email_verified_customer.id}",
            json={"metadata": {"test": "test"}},
        )

        assert response.status_code == 200

        json = response.json()
        assert json["metadata"] == {"test": "test"}

    @pytest.mark.auth
    async def test_empty_external_id_converts_to_none(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        workspace: Workspace,
    ) -> None:
        # Create two customers with None external_id
        customer1 = await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer1@example.com",
            external_id=None,
        )
        customer2 = await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer2@example.com",
            external_id=None,
        )

        # Try to update customer1 with empty string external_id
        # This should be converted to None and not cause a conflict
        response = await client.patch(
            f"/api/customers/{customer1.id}",
            json={"external_id": ""},
        )

        assert response.status_code == 200
        json = response.json()
        assert json["external_id"] is None

    @pytest.mark.auth
    async def test_external_id_conflict(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace_membership: WorkspaceMembership,
        workspace: Workspace,
    ) -> None:
        # Create two customers, one with an external_id
        customer1 = await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer1@example.com",
            external_id="existing_id",
        )
        customer2 = await create_customer(
            save_fixture,
            workspace=workspace,
            email="customer2@example.com",
            external_id=None,
        )

        # Try to update customer2 with customer1's external_id
        # This should fail with a conflict error
        response = await client.patch(
            f"/api/customers/{customer2.id}",
            json={"external_id": "existing_id"},
        )

        assert response.status_code == 422
        json = response.json()
        assert any(
            "already exists" in str(error.get("msg", ""))
            for error in json.get("detail", [])
        )


# ── Delete Customer with Anonymize ──


@pytest.mark.asyncio
class TestDeleteCustomerWithAnonymize:
    """Tests for DELETE /customers/{id}?anonymize=true"""

    @pytest.mark.auth
    async def test_delete_with_anonymize(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """Customers should have name anonymized."""
        customer = await create_customer(
            save_fixture,
            workspace=workspace,
            email="individual@example.com",
            name="John Doe",
        )

        response = await client.delete(f"/api/customers/{customer.id}?anonymize=true")

        assert response.status_code == 204

        # Verify anonymization by fetching directly from DB
        # (API filters out deleted customers)
        deleted = await session.get(Customer, customer.id)
        assert deleted is not None

        # Email should be hashed
        assert deleted.email.endswith("@redacted.invalid")
        assert deleted.email_verified is False

        # Name should be hashed (64-char hex string from SHA-256)
        assert deleted.name is not None
        assert len(deleted.name) == 64
        assert deleted.name != "John Doe"

        # Customer should be marked as deleted
        assert deleted.deleted_at is not None

    @pytest.mark.auth
    async def test_preserves_external_id(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """External ID should be preserved for legal reasons."""
        customer = await create_customer(
            save_fixture,
            workspace=workspace,
            email="external@example.com",
            external_id="ext-123",
        )

        response = await client.delete(f"/api/customers/{customer.id}?anonymize=true")

        assert response.status_code == 204

        # Verify by fetching directly from DB
        deleted = await session.get(Customer, customer.id)
        assert deleted is not None

        # External ID should be PRESERVED
        assert deleted.external_id == "ext-123"

    @pytest.mark.auth
    async def test_delete_without_anonymize(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """Delete without anonymize should not anonymize data."""
        customer = await create_customer(
            save_fixture,
            workspace=workspace,
            email="noanon@example.com",
            name="No Anon User",
        )

        response = await client.delete(f"/api/customers/{customer.id}")

        assert response.status_code == 204

        # Verify customer is deleted but NOT anonymized (fetch from DB)
        deleted = await session.get(Customer, customer.id)
        assert deleted is not None

        # Email should NOT be hashed
        assert deleted.email == "noanon@example.com"

        # Name should NOT be hashed
        assert deleted.name == "No Anon User"

        # Customer should be marked as deleted
        assert deleted.deleted_at is not None


# ── Delete Customer by External ID with Anonymize ──


@pytest.mark.asyncio
class TestDeleteCustomerExternalWithAnonymize:
    """Tests for DELETE /customers/external/{external_id}?anonymize=true"""

    @pytest.mark.auth
    async def test_delete_with_anonymize(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        customer = await create_customer(
            save_fixture,
            workspace=workspace,
            email="external-anon@example.com",
            external_id="ext-anon-123",
            name="External User",
        )

        response = await client.delete(
            f"/api/customers/external/{customer.external_id}?anonymize=true"
        )

        assert response.status_code == 204

        # Verify by fetching directly from DB
        deleted = await session.get(Customer, customer.id)
        assert deleted is not None

        # Email should be hashed
        assert deleted.email.endswith("@redacted.invalid")

        # External ID should be preserved
        assert deleted.external_id == "ext-anon-123"
