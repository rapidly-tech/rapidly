"""Tests for ``rapidly/core/oauth.py``.

The OAuth helpers manage the ephemeral state that lives between the
authorization redirect and the provider callback. This module is
security-sensitive:

- Timing-constant comparison of state vs. nonce cookie (``secrets
  .compare_digest``) resists timing attacks on the session check.
- State is deleted after retrieval so a leaked callback URL cannot
  be replayed.
- Cross-site flows (Apple Sign In POST callback) deliberately skip the
  cookie check because SameSite=None would weaken CSRF protection;
  the Redis-backed state param alone verifies the caller.
- Cookies demand ``secure=True`` everywhere except localhost.

None of this was exercised — pinning it here catches any regression
that silently relaxes one of the defences.
"""

from __future__ import annotations

import json
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from fastapi.responses import RedirectResponse

from rapidly.config import settings
from rapidly.core.oauth import (
    OAuthCallbackError,
    _cache_key,
    _requires_secure,
    clear_login_cookie,
    delete_oauth_state,
    retrieve_oauth_state,
    set_login_cookie,
    store_oauth_state,
    validate_callback,
)
from rapidly.redis import Redis

# ── Helpers ──


class FakeRedis:
    """In-memory Redis stub supporting the ``setex``/``get``/``delete``
    surface the module uses."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


def _fake_redis() -> Redis:
    """Return a FakeRedis typed as the real Redis client."""
    return cast("Redis", FakeRedis())


def _store(redis: Redis) -> dict[str, str]:
    """Expose the FakeRedis internal dict for direct assertions."""
    return cast("FakeRedis", redis).store


def _make_request(
    hostname: str = "example.test", cookies: dict[str, str] | None = None
) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "path": "/callback",
        "raw_path": b"/callback",
        "query_string": b"",
        "server": (hostname, 443),
        "headers": [(b"host", hostname.encode())],
    }
    if cookies:
        cookie_hdr = "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()
        scope["headers"].append((b"cookie", cookie_hdr))
    return Request(scope=scope)


# ── Tests ──


class TestCacheKey:
    def test_includes_provider_for_isolation(self) -> None:
        # Different providers must not share key space — a cross-provider
        # collision would let a microsoft nonce satisfy a google callback.
        assert _cache_key("microsoft", "nonce") != _cache_key("google", "nonce")

    def test_has_oauth_state_prefix(self) -> None:
        # Prefix-scoped keys keep OAuth state separate from other
        # Redis usage (rate limits, invites, …).
        assert _cache_key("google", "nonce").startswith("oauth_state:")


@pytest.mark.asyncio
class TestStateStoreRoundtrip:
    async def test_store_then_retrieve(self) -> None:
        redis = _fake_redis()
        await store_oauth_state(redis, "n1", {"k": "v"}, type="google")
        state = await retrieve_oauth_state(redis, "n1", type="google")
        assert state == {"k": "v"}

    async def test_retrieve_missing_raises_invalid_state(self) -> None:
        redis = _fake_redis()
        with pytest.raises(OAuthCallbackError, match="Invalid state"):
            await retrieve_oauth_state(redis, "missing", type="google")

    async def test_delete_removes_the_entry(self) -> None:
        redis = _fake_redis()
        await store_oauth_state(redis, "n1", {"k": "v"}, type="google")
        await delete_oauth_state(redis, "n1", type="google")
        with pytest.raises(OAuthCallbackError):
            await retrieve_oauth_state(redis, "n1", type="google")

    async def test_provider_isolation_on_retrieve(self) -> None:
        # A nonce stored under "microsoft" must not be readable via a
        # "google" lookup. Cross-provider replay defence.
        redis = _fake_redis()
        await store_oauth_state(redis, "n1", {"k": "v"}, type="microsoft")
        with pytest.raises(OAuthCallbackError):
            await retrieve_oauth_state(redis, "n1", type="google")

    async def test_state_is_json_serialised_in_store(self) -> None:
        # Pin JSON-serialisation so a regression that pickled the
        # payload (RCE surface on deserialise) would show up.
        redis = _fake_redis()
        await store_oauth_state(redis, "n1", {"k": "v"}, type="google")
        raw = _store(redis)[_cache_key("google", "n1")]
        assert json.loads(raw) == {"k": "v"}


class TestRequiresSecure:
    def test_localhost_is_not_secure(self) -> None:
        assert _requires_secure(_make_request("localhost")) is False

    def test_127_0_0_1_is_not_secure(self) -> None:
        assert _requires_secure(_make_request("127.0.0.1")) is False

    def test_public_host_is_secure(self) -> None:
        # Secure=True is REQUIRED on any non-localhost request — a
        # regression flipping this would let the nonce cookie travel
        # over http and be harvested by a MITM.
        assert _requires_secure(_make_request("dashboard.example.test")) is True


class TestCookieHelpers:
    def test_set_login_cookie_writes_httponly_lax_cookie(self) -> None:
        request = _make_request("dashboard.example.test")
        response = RedirectResponse(url="/", status_code=303)
        set_login_cookie(request, response, nonce="nonce123")
        header = response.headers.get("set-cookie", "")
        assert settings.OAUTH_STATE_COOKIE_KEY in header
        assert "nonce123" in header
        assert "HttpOnly" in header
        assert "Secure" in header
        # Lax is the default CSRF-safe SameSite for dashboard flows.
        assert "SameSite=lax" in header or "samesite=lax" in header.lower()

    def test_set_login_cookie_omits_secure_on_localhost(self) -> None:
        request = _make_request("localhost")
        response = RedirectResponse(url="/", status_code=303)
        set_login_cookie(request, response, nonce="n")
        assert "Secure" not in response.headers.get("set-cookie", "")

    def test_cross_site_skips_cookie_entirely(self) -> None:
        # Apple Sign In POST callbacks arrive with SameSite=None, which
        # weakens CSRF. Skipping the cookie is the documented safe
        # choice — the Redis-backed state param alone verifies.
        request = _make_request("example.test")
        response = RedirectResponse(url="/", status_code=303)
        set_login_cookie(request, response, nonce="n", cross_site=True)
        assert "set-cookie" not in response.headers

    def test_clear_login_cookie_expires_it(self) -> None:
        request = _make_request("example.test")
        response = RedirectResponse(url="/", status_code=303)
        clear_login_cookie(request, response)
        header = response.headers.get("set-cookie", "")
        assert "Max-Age=0" in header

    def test_clear_login_cookie_skips_on_cross_site(self) -> None:
        request = _make_request("example.test")
        response = RedirectResponse(url="/", status_code=303)
        clear_login_cookie(request, response, cross_site=True)
        assert "set-cookie" not in response.headers


@pytest.mark.asyncio
class TestValidateCallback:
    async def _setup(
        self, nonce: str = "nonce-x", payload: dict[str, Any] | None = None
    ) -> tuple[Redis, Any]:
        redis = _fake_redis()
        await store_oauth_state(
            redis, nonce, payload if payload is not None else {"k": "v"}, type="google"
        )
        return redis, payload if payload is not None else {"k": "v"}

    async def test_provider_error_description_raises(self) -> None:
        redis, _ = await self._setup()
        token = MagicMock()
        token.get = MagicMock(return_value="denied")
        request = _make_request(cookies={settings.OAUTH_STATE_COOKIE_KEY: "nonce-x"})
        with pytest.raises(OAuthCallbackError, match="denied"):
            await validate_callback(
                request, redis, token, state="nonce-x", type="google"
            )

    async def test_missing_state_raises_no_state(self) -> None:
        redis, _ = await self._setup()
        token = MagicMock()
        token.get = MagicMock(return_value=None)
        request = _make_request()
        with pytest.raises(OAuthCallbackError, match="No state"):
            await validate_callback(request, redis, token, state=None, type="google")

    async def test_missing_cookie_raises_invalid_session(self) -> None:
        # No cookie set — must NOT fall through to the Redis lookup.
        redis, _ = await self._setup()
        token = MagicMock()
        token.get = MagicMock(return_value=None)
        request = _make_request()
        with pytest.raises(OAuthCallbackError, match="Invalid session cookie"):
            await validate_callback(
                request, redis, token, state="nonce-x", type="google"
            )

    async def test_cookie_mismatch_raises_invalid_session(self) -> None:
        # Cookie does NOT match state — CSRF defence fires before
        # any Redis lookup.
        redis, _ = await self._setup()
        token = MagicMock()
        token.get = MagicMock(return_value=None)
        request = _make_request(
            cookies={settings.OAUTH_STATE_COOKIE_KEY: "different-nonce"}
        )
        with pytest.raises(OAuthCallbackError, match="Invalid session cookie"):
            await validate_callback(
                request, redis, token, state="nonce-x", type="google"
            )

    async def test_valid_callback_returns_payload_and_deletes_state(self) -> None:
        # Happy path: cookie matches, state is present in Redis.
        # Post-validation the entry MUST be gone — replay defence.
        redis, payload = await self._setup(payload={"email": "alice@test"})
        token = MagicMock()
        token.get = MagicMock(return_value=None)
        request = _make_request(cookies={settings.OAUTH_STATE_COOKIE_KEY: "nonce-x"})
        got = await validate_callback(
            request, redis, token, state="nonce-x", type="google"
        )
        assert got == payload
        # Entry is deleted after one retrieval.
        assert _cache_key("google", "nonce-x") not in _store(redis)

    async def test_cross_site_skips_cookie_check_but_still_verifies_redis(
        self,
    ) -> None:
        # For cross-site flows the cookie was never set; validation
        # relies on the Redis-backed state alone.
        redis, payload = await self._setup()
        token = MagicMock()
        token.get = MagicMock(return_value=None)
        request = _make_request()  # no cookie
        got = await validate_callback(
            request,
            redis,
            token,
            state="nonce-x",
            type="google",
            cross_site=True,
        )
        assert got == payload
        # Still deleted post-validation.
        assert _cache_key("google", "nonce-x") not in _store(redis)

    async def test_cross_site_still_requires_valid_redis_state(self) -> None:
        # Cross-site relaxes the COOKIE check, NOT the Redis check.
        # An attacker with a guessed state but no Redis entry must
        # still be rejected.
        redis = _fake_redis()  # empty
        token = MagicMock()
        token.get = MagicMock(return_value=None)
        request = _make_request()
        with pytest.raises(OAuthCallbackError, match="Invalid state"):
            await validate_callback(
                request,
                redis,
                token,
                state="guess",
                type="google",
                cross_site=True,
            )


class TestCreateAuthorizationResponseExerciseIsIntegration:
    # ``create_authorization_response`` mixes ``secrets.token_urlsafe``
    # + Redis + the OAuth client. The non-IO parts are already covered
    # above; exercising the helper with a mock oauth client ensures the
    # wiring stays intact (nonce stored, cookie set, 303 returned).

    @pytest.mark.asyncio
    async def test_happy_path_wires_nonce_to_redis_and_cookie(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from rapidly.core import oauth

        oauth_client = MagicMock()
        oauth_client.get_authorization_url = AsyncMock(
            return_value="https://provider.test/authorize"
        )

        redis = _fake_redis()
        request = _make_request()

        # Stub url_for — the real FastAPI request doesn't have routes.
        monkeypatch.setattr(type(request), "url_for", lambda self, name: "/callback")

        # Force a known nonce for deterministic assertion.
        monkeypatch.setattr(
            "rapidly.core.oauth.secrets.token_urlsafe", lambda *_: "fixed-nonce"
        )

        response = await oauth.create_authorization_response(
            request,
            redis,
            state={"return_to": "/"},
            callback_route="cb",
            oauth_client=oauth_client,
            scopes=["email"],
            type="google",
        )

        assert response.status_code == 303
        assert response.headers["location"] == "https://provider.test/authorize"
        # Nonce persisted with the state payload augmented by the nonce.
        assert json.loads(_store(redis)[_cache_key("google", "fixed-nonce")]) == {
            "return_to": "/",
            "nonce": "fixed-nonce",
        }
        assert "fixed-nonce" in response.headers.get("set-cookie", "")
