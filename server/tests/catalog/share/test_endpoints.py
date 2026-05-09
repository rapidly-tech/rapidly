"""Tests for share endpoints."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from rapidly.models import (
    Share,
    SharePriceFixed,
    Workspace,
    WorkspaceMembership,
)
from rapidly.models.custom_field import CustomFieldType
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import (
    create_custom_field,
    create_product,
)

# ── List Products ──


@pytest.mark.asyncio
class TestListProducts:
    async def test_anonymous(self, client: AsyncClient, workspace: Workspace) -> None:
        response = await client.get(
            "/api/shares/",
            params={"workspace_id": str(workspace.id)},
        )

        assert response.status_code == 401


# ── Get Share ──


@pytest.mark.asyncio
class TestGetProduct:
    async def test_anonymous(self, client: AsyncClient, share: Share) -> None:
        response = await client.get(f"/api/shares/{share.id}")

        assert response.status_code == 401

    @pytest.mark.auth
    async def test_not_existing(self, client: AsyncClient) -> None:
        response = await client.get(f"/api/shares/{uuid.uuid4()}")

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_valid(
        self,
        client: AsyncClient,
        share: Share,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.get(f"/api/shares/{share.id}")

        assert response.status_code == 200

        json = response.json()
        assert json["id"] == str(share.id)


# ── Create Share ──


@pytest.mark.asyncio
class TestCreateProduct:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/shares/",
            json={
                "type": "individual",
                "name": "Share",
                "price_amount": 2000,
                "workspace_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 401

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "ab"},
            {"name": ""},
            # No price
            {"prices": []},
            # Two prices
            {
                "prices": [
                    {"amount_type": "fixed", "price_amount": 1000},
                    {"amount_type": "fixed", "price_amount": 10000},
                ]
            },
        ],
    )
    @pytest.mark.auth
    async def test_validation(
        self,
        payload: dict[str, Any],
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
        session: AsyncSession,
    ) -> None:
        response = await client.post(
            "/api/shares/",
            json={
                "name": "Share",
                "workspace_id": str(workspace.id),
                "prices": [
                    {
                        "amount_type": "fixed",
                        "price_amount": 2000,
                        "price_currency": "usd",
                    }
                ],
                **payload,
            },
        )

        assert response.status_code == 422

    @pytest.mark.auth
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {
                    "recurring_interval": None,
                    "prices": [
                        {
                            "amount_type": "fixed",
                            "price_amount": 2000,
                            "price_currency": "usd",
                        }
                    ],
                },
                id="One-time fixed",
            ),
            pytest.param(
                {
                    "recurring_interval": None,
                    "prices": [
                        {
                            "amount_type": "custom",
                            "minimum_amount": 2000,
                            "price_currency": "usd",
                        }
                    ],
                },
                id="One-time custom",
            ),
            pytest.param(
                {
                    "recurring_interval": None,
                    "prices": [
                        {
                            "amount_type": "free",
                            "price_currency": "usd",
                        }
                    ],
                },
                id="One-time free",
            ),
            pytest.param(
                {
                    "recurring_interval": "day",
                    "prices": [
                        {
                            "amount_type": "fixed",
                            "price_amount": 2000,
                            "price_currency": "usd",
                        }
                    ],
                },
                id="Recurring daily fixed",
            ),
            pytest.param(
                {
                    "recurring_interval": "week",
                    "prices": [
                        {
                            "amount_type": "fixed",
                            "price_amount": 2000,
                            "price_currency": "usd",
                        }
                    ],
                },
                id="Recurring weekly fixed",
            ),
            pytest.param(
                {
                    "recurring_interval": "month",
                    "prices": [
                        {
                            "amount_type": "fixed",
                            "price_amount": 2000,
                            "price_currency": "usd",
                        }
                    ],
                },
                id="Recurring monthly fixed",
            ),
            pytest.param(
                {
                    "recurring_interval": "year",
                    "prices": [
                        {
                            "amount_type": "fixed",
                            "price_amount": 2000,
                            "price_currency": "usd",
                        }
                    ],
                },
                id="Recurring yearly fixed",
            ),
            pytest.param(
                {
                    "recurring_interval": "month",
                    "prices": [
                        {
                            "amount_type": "custom",
                            "minimum_amount": 2000,
                            "price_currency": "usd",
                        }
                    ],
                },
                id="Recurring custom",
            ),
            pytest.param(
                {
                    "recurring_interval": "month",
                    "prices": [
                        {
                            "amount_type": "free",
                            "price_currency": "usd",
                        }
                    ],
                },
                id="Recurring free",
            ),
            pytest.param(
                {
                    "recurring_interval": "month",
                    "recurring_interval_count": 3,
                    "prices": [
                        {
                            "amount_type": "fixed",
                            "price_amount": 2000,
                            "price_currency": "usd",
                        }
                    ],
                },
                id="Recurring with interval count",
            ),
        ],
    )
    async def test_valid(
        self,
        payload: dict[str, Any],
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.post(
            "/api/shares/",
            json={
                "name": "Share",
                "workspace_id": str(workspace.id),
                **payload,
            },
        )

        assert response.status_code == 201


# ── Update Share ──


@pytest.mark.asyncio
class TestUpdateProduct:
    async def test_anonymous(self, client: AsyncClient, share: Share) -> None:
        response = await client.patch(
            f"/api/shares/{share.id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 401

    @pytest.mark.auth
    async def test_not_existing(self, client: AsyncClient) -> None:
        response = await client.patch(
            f"/api/shares/{uuid.uuid4()}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 404

    @pytest.mark.auth
    async def test_valid(
        self,
        client: AsyncClient,
        share: Share,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.patch(
            f"/api/shares/{share.id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200

        json = response.json()
        assert json["name"] == "Updated Name"

    @pytest.mark.auth
    async def test_existing_price_with_full_schema(
        self,
        client: AsyncClient,
        product_one_time: Share,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        """
        We should handle the case where we want to keep the existing price, but we pass
        the full schema of it.

        It happens from the frontend where it's cumbersome
        to get rid of the full schema.
        """
        response = await client.patch(
            f"/api/shares/{product_one_time.id}",
            json={
                "prices": [
                    {
                        "id": str(product_one_time.prices[0].id),
                        "price_amount": 2000,
                        "price_currency": "usd",
                        "is_archived": False,
                        "amount_type": "fixed",
                    }
                ]
            },
        )

        assert response.status_code == 200

        json = response.json()
        assert len(json["prices"]) == 1
        price = json["prices"][0]
        assert price["id"] == str(product_one_time.prices[0].id)

        product_price = product_one_time.prices[0]
        assert isinstance(product_price, SharePriceFixed)
        assert price["price_amount"] == product_price.price_amount

    @pytest.mark.auth
    async def test_invalid_attached_custom_fields(
        self,
        save_fixture: SaveFixture,
        session: AsyncSession,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        custom_field = await create_custom_field(
            save_fixture,
            type=CustomFieldType.text,
            slug="test-field",
            workspace=workspace,
        )
        share = await create_product(
            save_fixture,
            workspace=workspace,
            attached_custom_fields=[
                (custom_field, True),
            ],
        )

        response = await client.patch(
            f"/api/shares/{share.id}",
            json={
                "attached_custom_fields": [
                    {
                        "custom_field_id": str(uuid.uuid4()),
                        "required": False,
                    }
                ]
            },
        )

        assert response.status_code == 422
