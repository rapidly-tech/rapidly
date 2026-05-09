"""HTTP tests for the Collab chamber endpoints (``/api/v1/collab/*``)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from rapidly.config import settings


@pytest.fixture(autouse=True)
def _enable_collab_chamber(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "FILE_SHARING_COLLAB_ENABLED", True)


@pytest.mark.asyncio
class TestCreateCollabSessionEndpoint:
    async def test_returns_payload_with_slugs_and_secret(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/collab/session",
            json={"title": "Sprint", "max_participants": 6, "kind": "text"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["short_slug"]
        assert body["secret"]
        assert body["invite_template"].startswith("/collab/")

    async def test_accepts_minimum_body(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/collab/session", json={})
        assert response.status_code == 200

    async def test_rejects_max_participants_over_cap(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/collab/session", json={"max_participants": 9}
        )
        assert response.status_code == 422

    async def test_rejects_max_participants_below_two(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/collab/session", json={"max_participants": 1}
        )
        assert response.status_code == 422

    async def test_rejects_invalid_kind(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/collab/session", json={"kind": "spreadsheet"}
        )
        assert response.status_code == 422

    async def test_404_when_feature_disabled(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "FILE_SHARING_COLLAB_ENABLED", False)
        response = await client.post("/api/v1/collab/session", json={})
        assert response.status_code == 404


@pytest.mark.asyncio
class TestMintInviteEndpoint:
    async def test_returns_token_for_valid_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/collab/session", json={"max_participants": 4})
        ).json()
        response = await client.post(
            f"/api/v1/collab/session/{created['short_slug']}/invite",
            json={"secret": created["secret"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["invite_token"]
        assert body["invite_url"].startswith(f"/collab/{created['short_slug']}")

    async def test_returns_404_for_wrong_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/collab/session", json={"max_participants": 4})
        ).json()
        response = await client.post(
            f"/api/v1/collab/session/{created['short_slug']}/invite",
            json={"secret": "wrong"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestGetCollabSessionEndpoint:
    async def test_returns_public_view_without_secrets(
        self, client: AsyncClient
    ) -> None:
        created = (
            await client.post(
                "/api/v1/collab/session",
                json={"title": "Writing", "max_participants": 4, "kind": "text"},
            )
        ).json()
        response = await client.get(f"/api/v1/collab/session/{created['short_slug']}")
        assert response.status_code == 200
        body = response.json()
        assert body["short_slug"] == created["short_slug"]
        assert body["title"] == "Writing"
        assert body["max_participants"] == 4
        assert body["kind"] == "text"
        assert "secret" not in body
        assert "invite_token" not in body

    async def test_returns_404_for_unknown_session(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/collab/session/missing")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCloseCollabSessionEndpoint:
    async def test_returns_204_on_success(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/collab/session", json={"max_participants": 3})
        ).json()
        response = await client.request(
            "DELETE",
            f"/api/v1/collab/session/{created['short_slug']}",
            json={"secret": created["secret"]},
        )
        assert response.status_code == 204

    async def test_returns_404_on_wrong_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/collab/session", json={"max_participants": 3})
        ).json()
        response = await client.request(
            "DELETE",
            f"/api/v1/collab/session/{created['short_slug']}",
            json={"secret": "wrong"},
        )
        assert response.status_code == 404
