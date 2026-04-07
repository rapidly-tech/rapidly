"""Tests for workspace access token endpoints."""

import pytest
from httpx import AsyncClient

from rapidly.models import Workspace, WorkspaceMembership


@pytest.mark.asyncio
class TestCreateWorkspaceAccessToken:
    @pytest.mark.parametrize("expires_in", [None, 3600])
    @pytest.mark.auth
    async def test_valid(
        self,
        expires_in: int | None,
        client: AsyncClient,
        workspace: Workspace,
        workspace_membership: WorkspaceMembership,
    ) -> None:
        response = await client.post(
            "/api/workspace-access-tokens/",
            json={
                "workspace_id": str(workspace.id),
                "comment": "hello world",
                "scopes": ["metrics:read"],
                "expires_in": expires_in,
            },
        )

        assert response.status_code == 201

        json = response.json()
        assert "workspace_access_token" in response.json()
        assert "token" in json
