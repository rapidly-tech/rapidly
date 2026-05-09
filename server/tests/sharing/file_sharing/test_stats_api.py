"""HTTP tests for the public stats endpoint (``/api/file-sharing/stats``).

Backstops the authorization rule introduced in #613: ``?workspace_id=X``
must require the caller be a member of that workspace; without the
check the count would be an enumeration vector for measuring
arbitrary workspaces' activity.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestPublicStats:
    async def test_anonymous_no_workspace_returns_count(
        self, client: AsyncClient
    ) -> None:
        """The public path stays public — anyone can read the global total."""
        response = await client.get("/api/file-sharing/stats")
        assert response.status_code == 200
        body = response.json()
        assert "total_shares" in body
        assert isinstance(body["total_shares"], int)
        assert body["total_shares"] >= 0


@pytest.mark.asyncio
class TestWorkspaceStatsAuthz:
    async def test_anonymous_with_workspace_id_is_unauthorized(
        self, client: AsyncClient
    ) -> None:
        """Regression for #613: anonymous + ``?workspace_id=X`` must 401.

        Pre-#613 this returned 200 with the workspace's count, letting any
        caller probe arbitrary workspace UUIDs to measure activity.
        """
        response = await client.get(f"/api/file-sharing/stats?workspace_id={uuid4()}")
        assert response.status_code == 401
