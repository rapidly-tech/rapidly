"""HTTP tests for the Call chamber endpoints (``/api/v1/call/*``)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from rapidly.config import settings


@pytest.fixture(autouse=True)
def _enable_call_chamber(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "FILE_SHARING_CALL_ENABLED", True)


@pytest.mark.asyncio
class TestCreateCallSessionEndpoint:
    async def test_returns_payload_with_slugs_and_secret(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/call/session",
            json={"title": "Daily", "max_participants": 3, "mode": "audio_video"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["short_slug"]
        assert body["secret"]
        assert body["invite_template"].startswith("/call/")

    async def test_accepts_minimum_body(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/call/session", json={})
        assert response.status_code == 200

    async def test_rejects_max_participants_over_cap(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/call/session", json={"max_participants": 5}
        )
        assert response.status_code == 422

    async def test_rejects_max_participants_below_two(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/call/session", json={"max_participants": 1}
        )
        assert response.status_code == 422

    async def test_rejects_invalid_mode(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/call/session", json={"mode": "video_only"}
        )
        assert response.status_code == 422

    async def test_404_when_feature_disabled(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "FILE_SHARING_CALL_ENABLED", False)
        response = await client.post("/api/v1/call/session", json={})
        assert response.status_code == 404


@pytest.mark.asyncio
class TestMintInviteEndpoint:
    async def test_returns_token_for_valid_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/call/session", json={"max_participants": 3})
        ).json()
        response = await client.post(
            f"/api/v1/call/session/{created['short_slug']}/invite",
            json={"secret": created["secret"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["invite_token"]
        assert body["invite_url"].startswith(f"/call/{created['short_slug']}")

    async def test_returns_404_for_wrong_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/call/session", json={"max_participants": 3})
        ).json()
        response = await client.post(
            f"/api/v1/call/session/{created['short_slug']}/invite",
            json={"secret": "wrong"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestGetCallSessionEndpoint:
    async def test_returns_public_view_without_secrets(
        self, client: AsyncClient
    ) -> None:
        created = (
            await client.post(
                "/api/v1/call/session",
                json={"title": "Standup", "max_participants": 4},
            )
        ).json()
        response = await client.get(f"/api/v1/call/session/{created['short_slug']}")
        assert response.status_code == 200
        body = response.json()
        assert body["short_slug"] == created["short_slug"]
        assert body["title"] == "Standup"
        assert body["max_participants"] == 4
        assert body["mode"] == "audio_video"
        assert "secret" not in body
        assert "invite_token" not in body

    async def test_returns_404_for_unknown_session(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/call/session/missing")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCloseCallSessionEndpoint:
    async def test_returns_204_on_success(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/call/session", json={"max_participants": 3})
        ).json()
        response = await client.request(
            "DELETE",
            f"/api/v1/call/session/{created['short_slug']}",
            json={"secret": created["secret"]},
        )
        assert response.status_code == 204

    async def test_returns_404_on_wrong_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/call/session", json={"max_participants": 3})
        ).json()
        response = await client.request(
            "DELETE",
            f"/api/v1/call/session/{created['short_slug']}",
            json={"secret": "wrong"},
        )
        assert response.status_code == 404
