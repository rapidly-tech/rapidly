"""Tests for user API endpoints."""

import pytest
from httpx import AsyncClient

from rapidly.core.utils import now_utc
from rapidly.models import User, Workspace, WorkspaceMembership
from tests.fixtures.database import SaveFixture


@pytest.mark.asyncio
@pytest.mark.auth
async def test_get_users_me_authed(user: User, client: AsyncClient) -> None:
    response = await client.get("/api/users/me")

    assert response.status_code == 200
    json = response.json()

    assert json["email"] == user.email
    assert "oauth_accounts" in json


@pytest.mark.asyncio
async def test_get_users_me_no_auth(client: AsyncClient) -> None:
    response = await client.get("/api/users/me")

    assert response.status_code == 401


@pytest.mark.asyncio
class TestDeleteUser:
    async def test_anonymous(self, client: AsyncClient) -> None:
        response = await client.delete("/api/users/me")

        assert response.status_code == 401

    @pytest.mark.auth
    async def test_no_workspaces(
        self,
        client: AsyncClient,
        user: User,
    ) -> None:
        response = await client.delete("/api/users/me")

        assert response.status_code == 200
        json = response.json()
        assert json["deleted"] is True
        assert json["blocked_reasons"] == []
        assert json["blocking_workspaces"] == []

    @pytest.mark.auth
    async def test_blocked_with_active_workspace(
        self,
        client: AsyncClient,
        user: User,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.delete("/api/users/me")

        assert response.status_code == 200
        json = response.json()
        assert json["deleted"] is False
        assert "has_active_workspaces" in json["blocked_reasons"]
        assert len(json["blocking_workspaces"]) == 1
        assert json["blocking_workspaces"][0]["id"] == str(workspace.id)
        assert json["blocking_workspaces"][0]["slug"] == workspace.slug

    @pytest.mark.auth
    async def test_with_deleted_workspace(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        user: User,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        workspace.deleted_at = now_utc()
        await save_fixture(workspace)

        response = await client.delete("/api/users/me")

        assert response.status_code == 200
        json = response.json()
        assert json["deleted"] is True
        assert json["blocked_reasons"] == []

    @pytest.mark.auth
    async def test_pii_anonymization(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        user: User,
    ) -> None:
        user.avatar_url = "https://example.com/avatar.png"
        user.meta = {"signup": {"intent": "creator"}}
        await save_fixture(user)

        response = await client.delete("/api/users/me")

        assert response.status_code == 200
        json = response.json()
        assert json["deleted"] is True
