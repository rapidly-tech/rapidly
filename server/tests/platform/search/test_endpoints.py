"""Tests for search API endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from rapidly.identity.auth.scope import Scope
from rapidly.models import (
    Workspace,
    WorkspaceMembership,
)
from rapidly.postgres import AsyncSession
from tests.fixtures.auth import AuthSubjectFixture
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import (
    create_customer,
    create_product,
)


@pytest.mark.asyncio
class TestSearch:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.get(
            "/search",
            params={
                "workspace_id": str(uuid.uuid4()),
                "query": "test",
            },
        )
        assert response.status_code == 401

    @pytest.mark.auth
    async def test_not_member(
        self,
        client: AsyncClient,
        workspace: Workspace,
    ) -> None:
        response = await client.get(
            "/search",
            params={
                "workspace_id": str(workspace.id),
                "query": "test",
            },
        )
        assert response.status_code == 200
        json = response.json()
        assert json["results"] == []

    @pytest.mark.auth
    async def test_search_products_by_name(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        await create_product(
            save_fixture,
            workspace=workspace,
            name="Premium Plan",
        )

        response = await client.get(
            "/search",
            params={
                "workspace_id": str(workspace.id),
                "query": "Premium",
            },
        )
        assert response.status_code == 200
        json = response.json()
        assert len(json["results"]) >= 1
        assert any(
            r["type"] == "share" and r["name"] == "Premium Plan"
            for r in json["results"]
        )

    @pytest.mark.auth
    async def test_search_products_by_description(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        share = await create_product(
            save_fixture,
            workspace=workspace,
            name="Basic Plan",
        )
        share.description = "Includes free support"
        await save_fixture(share)

        response = await client.get(
            "/search",
            params={
                "workspace_id": str(workspace.id),
                "query": "free",
            },
        )
        assert response.status_code == 200
        json = response.json()
        assert len(json["results"]) >= 1
        assert any(
            r["type"] == "share" and r["name"] == "Basic Plan" for r in json["results"]
        )

    @pytest.mark.auth
    async def test_search_customers_by_email(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="test@example.com",
        )

        response = await client.get(
            "/search",
            params={
                "workspace_id": str(workspace.id),
                "query": "test@example",
            },
        )
        assert response.status_code == 200
        json = response.json()
        assert len(json["results"]) >= 1
        assert any(
            r["type"] == "customer" and r["email"] == "test@example.com"
            for r in json["results"]
        )

    @pytest.mark.auth
    async def test_search_partial_match(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        await create_product(
            save_fixture,
            workspace=workspace,
            name="Parrot Free",
        )

        response = await client.get(
            "/search",
            params={
                "workspace_id": str(workspace.id),
                "query": "Free",
            },
        )
        assert response.status_code == 200
        json = response.json()
        assert len(json["results"]) >= 1
        assert any(
            r["type"] == "share" and r["name"] == "Parrot Free" for r in json["results"]
        )

    @pytest.mark.auth(AuthSubjectFixture(scopes={Scope.shares_read}))
    async def test_search_with_only_products_scope(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        await create_product(
            save_fixture,
            workspace=workspace,
            name="Test Share",
        )
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="test@example.com",
        )

        response = await client.get(
            "/search",
            params={
                "workspace_id": str(workspace.id),
                "query": "Test",
            },
        )
        assert response.status_code == 200
        json = response.json()
        assert len(json["results"]) == 1
        assert all(r["type"] == "share" for r in json["results"])
        assert json["results"][0]["name"] == "Test Share"

    @pytest.mark.auth(AuthSubjectFixture(scopes={Scope.customers_read}))
    async def test_search_with_only_customers_scope(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        await create_product(
            save_fixture,
            workspace=workspace,
            name="Test Share",
        )
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="testuser@example.com",
        )

        response = await client.get(
            "/search",
            params={
                "workspace_id": str(workspace.id),
                "query": "test",
            },
        )
        assert response.status_code == 200
        json = response.json()
        assert len(json["results"]) == 1
        assert all(r["type"] == "customer" for r in json["results"])
        assert json["results"][0]["email"] == "testuser@example.com"

    @pytest.mark.auth(
        AuthSubjectFixture(scopes={Scope.shares_read, Scope.customers_read})
    )
    async def test_search_with_multiple_scopes(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        await create_product(
            save_fixture,
            workspace=workspace,
            name="Search Share",
        )
        await create_customer(
            save_fixture,
            workspace=workspace,
            email="search@example.com",
        )

        response = await client.get(
            "/search",
            params={
                "workspace_id": str(workspace.id),
                "query": "search",
            },
        )
        assert response.status_code == 200
        json = response.json()
        assert len(json["results"]) == 2
        result_types = {r["type"] for r in json["results"]}
        assert "share" in result_types
        assert "customer" in result_types

    @pytest.mark.auth(AuthSubjectFixture(scopes=set()))
    async def test_search_with_no_scopes(
        self,
        save_fixture: SaveFixture,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        await create_product(
            save_fixture,
            workspace=workspace,
            name="Test Share",
        )

        response = await client.get(
            "/search",
            params={
                "workspace_id": str(workspace.id),
                "query": "Test",
            },
        )
        assert response.status_code == 403
