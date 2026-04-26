"""HTTP tests for the Screen chamber endpoints (``/api/v1/screen/*``).

Covers spec test #7 (status codes for each verb) and #8 (schema-level
``max_viewers`` cap). The feature flag is flipped on via
``monkeypatch.setattr`` so we exercise the live routes without changing
the default deploy posture.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from rapidly.config import settings


@pytest.fixture(autouse=True)
def _enable_screen_chamber(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flip the feature flag on for every test in this module.

    The flag defaults to False in production so the endpoints 404 on
    unenabled deployments; tests need it True to exercise the live
    responses.
    """
    monkeypatch.setattr(settings, "FILE_SHARING_SCREEN_ENABLED", True)


@pytest.mark.asyncio
class TestCreateScreenSessionEndpoint:
    async def test_returns_201_like_payload_with_slugs_and_secret(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/screen/session",
            json={"title": "Demo", "max_viewers": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["short_slug"]
        assert body["long_slug"]
        assert body["secret"]
        assert body["invite_template"].startswith("/screen/")
        assert body["expires_at"]

    async def test_accepts_minimum_body(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/screen/session", json={})
        assert response.status_code == 200

    async def test_rejects_max_viewers_over_cap(self, client: AsyncClient) -> None:
        """Spec test #8 — the 10-viewer cap is enforced at the schema
        level so no request can reach the action layer with a larger
        value, regardless of any future call-site mistakes."""
        response = await client.post(
            "/api/v1/screen/session",
            json={"max_viewers": 11},
        )
        assert response.status_code == 422

    async def test_rejects_max_viewers_below_one(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/screen/session",
            json={"max_viewers": 0},
        )
        assert response.status_code == 422

    async def test_404_when_feature_disabled(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "FILE_SHARING_SCREEN_ENABLED", False)
        response = await client.post("/api/v1/screen/session", json={})
        assert response.status_code == 404


@pytest.mark.asyncio
class TestMintInviteEndpoint:
    async def test_returns_token_for_valid_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post(
                "/api/v1/screen/session",
                json={"max_viewers": 3},
            )
        ).json()
        response = await client.post(
            f"/api/v1/screen/session/{created['short_slug']}/invite",
            json={"secret": created["secret"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["invite_token"]
        assert body["invite_url"].startswith(f"/screen/{created['short_slug']}")

    async def test_returns_404_for_wrong_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/screen/session", json={"max_viewers": 3})
        ).json()
        response = await client.post(
            f"/api/v1/screen/session/{created['short_slug']}/invite",
            json={"secret": "wrong"},
        )
        assert response.status_code == 404

    async def test_returns_404_for_unknown_slug(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/screen/session/nonexistent/invite",
            json={"secret": "anything"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestGetScreenSessionEndpoint:
    async def test_returns_public_view_without_secrets(
        self, client: AsyncClient
    ) -> None:
        created = (
            await client.post(
                "/api/v1/screen/session",
                json={"title": "Standup", "max_viewers": 4},
            )
        ).json()
        response = await client.get(f"/api/v1/screen/session/{created['short_slug']}")
        assert response.status_code == 200
        body = response.json()
        assert body["short_slug"] == created["short_slug"]
        assert body["title"] == "Standup"
        assert body["max_viewers"] == 4
        assert body["started_at"]
        # Security: the public landing must not expose host credentials.
        assert "secret" not in body
        assert "invite_token" not in body

    async def test_returns_404_for_unknown_session(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/screen/session/missing")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCloseScreenSessionEndpoint:
    async def test_returns_204_on_success(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/screen/session", json={"max_viewers": 3})
        ).json()
        response = await client.request(
            "DELETE",
            f"/api/v1/screen/session/{created['short_slug']}",
            json={"secret": created["secret"]},
        )
        assert response.status_code == 204
        # Follow-up GET returns 404 — the session is truly gone.
        follow_up = await client.get(f"/api/v1/screen/session/{created['short_slug']}")
        assert follow_up.status_code == 404

    async def test_returns_404_on_wrong_secret(self, client: AsyncClient) -> None:
        created = (
            await client.post("/api/v1/screen/session", json={"max_viewers": 3})
        ).json()
        response = await client.request(
            "DELETE",
            f"/api/v1/screen/session/{created['short_slug']}",
            json={"secret": "wrong"},
        )
        assert response.status_code == 404
