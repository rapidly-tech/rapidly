"""HTTP tests for the Watch chamber endpoints (``/api/v1/watch/*``)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from rapidly.config import settings


@pytest.fixture(autouse=True)
def _enable_watch_chamber(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "FILE_SHARING_WATCH_ENABLED", True)


@pytest.mark.asyncio
class TestCreateWatchSessionEndpoint:
    async def test_returns_payload_with_slugs_and_secret(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/watch/session",
            json={
                "title": "Trailer",
                "max_viewers": 5,
                "source_url": "https://example.com/v.mp4",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["short_slug"]
        assert body["secret"]
        assert body["invite_template"].startswith("/watch/")
        assert body["expires_at"]

    async def test_accepts_minimum_body(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/watch/session", json={})
        assert response.status_code == 200

    async def test_rejects_max_viewers_over_cap(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/watch/session", json={"max_viewers": 11})
        assert response.status_code == 422

    async def test_rejects_invalid_source_url(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/watch/session",
            json={"source_url": "not a url"},
        )
        assert response.status_code == 422

    async def test_404_when_feature_disabled(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "FILE_SHARING_WATCH_ENABLED", False)
        response = await client.post("/api/v1/watch/session", json={})
        assert response.status_code == 404


@pytest.mark.asyncio
class TestMintInviteEndpoint:
    async def test_returns_token_for_valid_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post(
                "/api/v1/watch/session",
                json={"max_viewers": 3},
            )
        ).json()
        response = await client.post(
            f"/api/v1/watch/session/{created['short_slug']}/invite",
            json={"secret": created["secret"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["invite_token"]
        assert body["invite_url"].startswith(f"/watch/{created['short_slug']}")

    async def test_returns_404_for_wrong_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/watch/session", json={"max_viewers": 3})
        ).json()
        response = await client.post(
            f"/api/v1/watch/session/{created['short_slug']}/invite",
            json={"secret": "wrong"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestGetWatchSessionEndpoint:
    async def test_returns_public_view_without_secrets(
        self, client: AsyncClient
    ) -> None:
        created = (
            await client.post(
                "/api/v1/watch/session",
                json={
                    "title": "Standup",
                    "max_viewers": 4,
                    "source_url": "https://example.com/x.mp4",
                },
            )
        ).json()
        response = await client.get(f"/api/v1/watch/session/{created['short_slug']}")
        assert response.status_code == 200
        body = response.json()
        assert body["short_slug"] == created["short_slug"]
        assert body["title"] == "Standup"
        assert body["source_url"] == "https://example.com/x.mp4"
        assert "secret" not in body
        assert "invite_token" not in body

    async def test_returns_404_for_unknown_session(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/watch/session/missing")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCloseWatchSessionEndpoint:
    async def test_returns_204_on_success(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/watch/session", json={"max_viewers": 3})
        ).json()
        response = await client.request(
            "DELETE",
            f"/api/v1/watch/session/{created['short_slug']}",
            json={"secret": created["secret"]},
        )
        assert response.status_code == 204

    async def test_returns_404_on_wrong_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/watch/session", json={"max_viewers": 3})
        ).json()
        response = await client.request(
            "DELETE",
            f"/api/v1/watch/session/{created['short_slug']}",
            json={"secret": "wrong"},
        )
        assert response.status_code == 404
