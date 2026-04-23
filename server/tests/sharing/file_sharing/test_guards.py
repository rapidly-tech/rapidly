"""Tests for ``rapidly/sharing/file_sharing/guards.py``.

``validate_slug`` is already covered by ``test_security.py``. This file
pins the remaining exported surface:

- ``extract_bearer_token`` — pure Authorization-header parser
- ``MAX_SECRET_BODY_SIZE`` + the rate-limit constants — security-
  load-bearing budget values whose silent drift would change the
  abuse-hardness of the HTTP surface
- ``check_rate_limit`` — fail-closed behaviour on Redis outage is a
  security invariant and is tested explicitly
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from redis import RedisError

from rapidly.redis import Redis
from rapidly.sharing.file_sharing.guards import (
    CHANNEL_ACTION_RATE_LIMIT,
    CHANNEL_ACTION_RATE_WINDOW,
    CHANNEL_CREATE_RATE_LIMIT,
    CHANNEL_CREATE_RATE_WINDOW,
    CHANNEL_FETCH_RATE_LIMIT,
    CHANNEL_FETCH_RATE_WINDOW,
    MAX_SECRET_BODY_SIZE,
    SECRET_CREATE_RATE_LIMIT,
    SECRET_CREATE_RATE_WINDOW,
    SECRET_FETCH_RATE_LIMIT,
    SECRET_FETCH_RATE_WINDOW,
    SECRET_METADATA_RATE_LIMIT,
    SECRET_METADATA_RATE_WINDOW,
    check_rate_limit,
    extract_bearer_token,
)

# ── extract_bearer_token ──


class TestExtractBearerToken:
    def test_returns_the_token_part_of_Bearer_header(self) -> None:
        assert extract_bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"

    def test_returns_none_for_none(self) -> None:
        assert extract_bearer_token(None) is None

    def test_returns_none_for_empty_string(self) -> None:
        assert extract_bearer_token("") is None

    def test_returns_none_for_non_bearer_scheme(self) -> None:
        # Basic / Digest / etc. must not be accepted — the bearer form
        # is what our middlewares expect.
        assert extract_bearer_token("Basic dXNlcjpwYXNz") is None
        assert extract_bearer_token("Digest username=x") is None

    def test_is_case_sensitive_on_the_scheme(self) -> None:
        # "bearer" lowercase is NOT valid per the guard (strict startswith
        # on "Bearer "). Pinning explicitly so a future refactor doesn't
        # silently widen acceptance.
        assert extract_bearer_token("bearer abc") is None
        assert extract_bearer_token("BEARER abc") is None

    def test_empty_token_after_prefix_still_returns_empty_string(self) -> None:
        # "Bearer " with no token returns "" — the caller must check for
        # truthiness, not just ``is None``.
        assert extract_bearer_token("Bearer ") == ""


# ── Rate-limit constants ──


class TestRateLimitConstants:
    """Pin the security-budget values. Silent drift here weakens the
    HTTP abuse surface — every value change should land in a PR with an
    explicit security review note."""

    def test_body_size_cap_is_2MB(self) -> None:
        # 2 MB = 1 MB payload + ~1 MB of JSON / base64 overhead.
        assert MAX_SECRET_BODY_SIZE == 2 * 1024 * 1024

    def test_channel_create_budget(self) -> None:
        # 20 channels per IP per 10 minutes.
        assert CHANNEL_CREATE_RATE_LIMIT == 20
        assert CHANNEL_CREATE_RATE_WINDOW == 600

    def test_channel_fetch_budget(self) -> None:
        # 60 requests per IP per minute.
        assert CHANNEL_FETCH_RATE_LIMIT == 60
        assert CHANNEL_FETCH_RATE_WINDOW == 60

    def test_channel_action_budget(self) -> None:
        assert CHANNEL_ACTION_RATE_LIMIT == 30
        assert CHANNEL_ACTION_RATE_WINDOW == 60

    def test_secret_create_budget(self) -> None:
        # 30 secret/file creations per IP per 10 minutes.
        assert SECRET_CREATE_RATE_LIMIT == 30
        assert SECRET_CREATE_RATE_WINDOW == 600

    def test_secret_fetch_budget(self) -> None:
        assert SECRET_FETCH_RATE_LIMIT == 60
        assert SECRET_FETCH_RATE_WINDOW == 60

    def test_secret_metadata_budget(self) -> None:
        assert SECRET_METADATA_RATE_LIMIT == 30
        assert SECRET_METADATA_RATE_WINDOW == 60

    def test_no_budget_is_zero_or_negative(self) -> None:
        # Degenerate values (0, -1) would either lock the endpoint out
        # entirely or effectively disable the limiter. Pin both windows
        # and limits stay positive.
        for v in [
            CHANNEL_CREATE_RATE_LIMIT,
            CHANNEL_CREATE_RATE_WINDOW,
            CHANNEL_FETCH_RATE_LIMIT,
            CHANNEL_FETCH_RATE_WINDOW,
            CHANNEL_ACTION_RATE_LIMIT,
            CHANNEL_ACTION_RATE_WINDOW,
            SECRET_CREATE_RATE_LIMIT,
            SECRET_CREATE_RATE_WINDOW,
            SECRET_FETCH_RATE_LIMIT,
            SECRET_FETCH_RATE_WINDOW,
            SECRET_METADATA_RATE_LIMIT,
            SECRET_METADATA_RATE_WINDOW,
            MAX_SECRET_BODY_SIZE,
        ]:
            assert v > 0


# ── check_rate_limit ──


def _mock_request(ip: str = "1.2.3.4") -> MagicMock:
    """A minimally-shaped FastAPI ``Request`` — only ``request.client.host``
    is read by ``check_rate_limit``."""
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = ip
    return req


@pytest.mark.asyncio
class TestCheckRateLimit:
    async def test_allows_requests_under_the_limit(self, redis: Redis) -> None:
        # First call — no prior state in fakeredis.
        await check_rate_limit(
            _mock_request(), redis, "test-action", limit=3, window=60
        )
        # No exception raised.

    async def test_allows_up_to_the_limit(self, redis: Redis) -> None:
        for _ in range(3):
            await check_rate_limit(
                _mock_request(), redis, "test-action", limit=3, window=60
            )
        # Still ok at exactly ``limit``.

    async def test_rejects_the_call_after_the_limit(self, redis: Redis) -> None:
        # 3 requests allowed; the 4th raises 429.
        for _ in range(3):
            await check_rate_limit(
                _mock_request(), redis, "test-action", limit=3, window=60
            )
        with pytest.raises(HTTPException) as excinfo:
            await check_rate_limit(
                _mock_request(), redis, "test-action", limit=3, window=60
            )
        assert excinfo.value.status_code == 429

    async def test_rejects_with_custom_detail_string(self, redis: Redis) -> None:
        for _ in range(2):
            await check_rate_limit(_mock_request(), redis, "x", limit=2, window=60)
        with pytest.raises(HTTPException) as excinfo:
            await check_rate_limit(
                _mock_request(),
                redis,
                "x",
                limit=2,
                window=60,
                detail="custom-msg",
            )
        assert excinfo.value.detail == "custom-msg"

    async def test_is_scoped_by_ip(self, redis: Redis) -> None:
        # Two different IPs each get the full budget.
        for _ in range(2):
            await check_rate_limit(
                _mock_request("1.1.1.1"), redis, "act", limit=2, window=60
            )
            await check_rate_limit(
                _mock_request("2.2.2.2"), redis, "act", limit=2, window=60
            )
        # Each IP has used 2 of 2; next one for either IP should 429.
        with pytest.raises(HTTPException):
            await check_rate_limit(
                _mock_request("1.1.1.1"), redis, "act", limit=2, window=60
            )

    async def test_is_scoped_by_action(self, redis: Redis) -> None:
        # Same IP, two different action names — each gets its own budget.
        for _ in range(2):
            await check_rate_limit(
                _mock_request(), redis, "action-a", limit=2, window=60
            )
            await check_rate_limit(
                _mock_request(), redis, "action-b", limit=2, window=60
            )

    async def test_falls_back_to_unknown_ip_when_client_is_missing(
        self, redis: Redis
    ) -> None:
        # request.client may be None for disconnected sockets / ASGI
        # transports that don't populate it. The guard must not crash.
        req = MagicMock()
        req.client = None
        # First call under the limit — doesn't raise.
        await check_rate_limit(req, redis, "nc", limit=2, window=60)

    async def test_fails_closed_on_redis_error(self) -> None:
        """Security-critical: if Redis is unavailable, the guard raises
        503 rather than letting the request through. Trading off
        availability for abuse-resistance is the documented design."""
        redis = AsyncMock()
        redis.eval = AsyncMock(side_effect=RedisError("boom"))
        with pytest.raises(HTTPException) as excinfo:
            await check_rate_limit(_mock_request(), redis, "act", limit=3, window=60)
        assert excinfo.value.status_code == 503
