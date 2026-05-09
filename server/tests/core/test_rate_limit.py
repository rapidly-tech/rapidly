"""Tests for ``rapidly/core/rate_limit.py``.

Two helpers, both security-sensitive:

- ``check_otp_rate_limit`` is the Redis-backed OTP brute-force
  defence used by the login-code + customer-portal session
  endpoints. Its load-bearing property is **fail-closed**: if Redis
  is unavailable, the request is REJECTED (not allowed through),
  preventing an outage from widening the brute-force surface on
  short OTP codes.
- ``inmemory_rate_check`` is the no-Redis fallback for single-process
  installations. Pinning its count → allow / count+1 → deny
  behaviour guards the boundary.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from fakeredis import FakeAsyncRedis
from fastapi import HTTPException

from rapidly.core import rate_limit as RL
from rapidly.core.rate_limit import (
    OTP_VERIFY_LIMIT,
    OTP_VERIFY_WINDOW,
    check_otp_rate_limit,
    inmemory_rate_check,
)

# ── OTP constants ──


class TestOTPConstants:
    def test_limit_and_window_are_pinned(self) -> None:
        # These are the brute-force budget for 6-digit OTP codes —
        # 10 tries per 15 minutes. Silently widening either would
        # materially raise the brute-force odds.
        assert OTP_VERIFY_LIMIT == 10
        assert OTP_VERIFY_WINDOW == 900


# ── check_otp_rate_limit (Redis-backed) ──


def _make_request(client_host: str = "192.0.2.1") -> Any:
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = client_host
    return req


@pytest.mark.asyncio
class TestCheckOTPRateLimit:
    async def test_allows_first_10_attempts(self) -> None:
        redis: Any = FakeAsyncRedis()
        req = _make_request()
        # 10 attempts is exactly at the limit (inclusive).
        for _ in range(OTP_VERIFY_LIMIT):
            await check_otp_rate_limit(redis, req, key_prefix="login")

    async def test_eleventh_attempt_raises_429(self) -> None:
        redis: Any = FakeAsyncRedis()
        req = _make_request()
        for _ in range(OTP_VERIFY_LIMIT):
            await check_otp_rate_limit(redis, req, key_prefix="login")
        # Attempt 11 must 429.
        with pytest.raises(HTTPException) as exc:
            await check_otp_rate_limit(redis, req, key_prefix="login")
        assert exc.value.status_code == 429

    async def test_distinct_prefixes_have_separate_buckets(self) -> None:
        # ``login`` and ``portal`` use different key prefixes — a
        # regression that dropped the prefix would let login attempts
        # eat into the portal budget (and vice versa).
        redis: Any = FakeAsyncRedis()
        req = _make_request()
        for _ in range(OTP_VERIFY_LIMIT):
            await check_otp_rate_limit(redis, req, key_prefix="login")
        # Fresh bucket for the portal prefix — no 429 on the first call.
        await check_otp_rate_limit(redis, req, key_prefix="portal")

    async def test_distinct_ips_have_separate_buckets(self) -> None:
        redis: Any = FakeAsyncRedis()
        for _ in range(OTP_VERIFY_LIMIT):
            await check_otp_rate_limit(
                redis, _make_request("198.51.100.1"), key_prefix="login"
            )
        # A different IP must start from 0, not share the cap.
        await check_otp_rate_limit(
            redis, _make_request("198.51.100.2"), key_prefix="login"
        )

    async def test_ip_key_is_hashed_not_stored_in_plaintext(self) -> None:
        # The key contains an HMAC of the IP, not the raw IP. An
        # operator scanning Redis should not see PII.
        redis: Any = FakeAsyncRedis()
        req = _make_request("203.0.113.42")
        await check_otp_rate_limit(redis, req, key_prefix="login")
        keys = [k.decode() for k in await redis.keys("otp-rate:login:*")]
        assert len(keys) == 1
        assert "203.0.113.42" not in keys[0]

    async def test_fails_closed_on_redis_outage(self) -> None:
        # Load-bearing security pin. When Redis is broken, the
        # helper must 503 rather than let through — otherwise an
        # attacker who can trip Redis (or a benign outage) would
        # remove the brute-force defence entirely.
        broken_redis = MagicMock()

        class _Pipe:
            async def __aenter__(self) -> _Pipe:
                raise RuntimeError("redis connection reset")

            async def __aexit__(self, *a: Any) -> None:
                return None

        broken_redis.pipeline = MagicMock(return_value=_Pipe())
        req = _make_request()
        with pytest.raises(HTTPException) as exc:
            await check_otp_rate_limit(broken_redis, req, key_prefix="login")
        assert exc.value.status_code == 503

    async def test_429_is_not_swallowed_by_except_exception(self) -> None:
        # ``raise HTTPException(429)`` happens inside the try block.
        # The module re-raises HTTPException before the broad
        # ``except Exception`` catches it. A regression that dropped
        # the ``except HTTPException: raise`` would 503 instead of
        # 429 on legitimate over-limit requests — user would see
        # "service unavailable" instead of "too many attempts".
        redis: Any = FakeAsyncRedis()
        req = _make_request()
        for _ in range(OTP_VERIFY_LIMIT):
            await check_otp_rate_limit(redis, req, key_prefix="login")
        with pytest.raises(HTTPException) as exc:
            await check_otp_rate_limit(redis, req, key_prefix="login")
        # Must be 429, never 503.
        assert exc.value.status_code == 429

    async def test_missing_client_uses_unknown_fallback(self) -> None:
        # ``request.client`` may be None on ASGI servers without a
        # peer — the helper falls back to "unknown" so it still
        # rate-limits (shared bucket for all None-client callers).
        redis: Any = FakeAsyncRedis()
        req = MagicMock()
        req.client = None
        await check_otp_rate_limit(redis, req, key_prefix="login")
        keys = [k.decode() for k in await redis.keys("otp-rate:login:*")]
        assert len(keys) == 1


# ── inmemory_rate_check ──


class TestInMemoryRateCheck:
    def setup_method(self) -> None:
        RL._inmemory_rate_limits.clear()
        RL._inmemory_last_cleanup = 0.0

    def test_first_call_allowed(self) -> None:
        assert inmemory_rate_check("k", limit=3, window=60) is True

    def test_allows_up_to_limit(self) -> None:
        for _ in range(3):
            assert inmemory_rate_check("k", limit=3, window=60) is True

    def test_rejects_over_limit(self) -> None:
        for _ in range(3):
            inmemory_rate_check("k", limit=3, window=60)
        # The 4th hit is over the limit.
        assert inmemory_rate_check("k", limit=3, window=60) is False

    def test_distinct_keys_have_separate_buckets(self) -> None:
        for _ in range(3):
            inmemory_rate_check("k1", limit=3, window=60)
        assert inmemory_rate_check("k2", limit=3, window=60) is True

    def test_expired_window_resets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Advance monotonic time past the window — the next call
        # must see a fresh bucket.
        t = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: t[0])
        for _ in range(3):
            inmemory_rate_check("k", limit=3, window=60)
        assert inmemory_rate_check("k", limit=3, window=60) is False
        t[0] = 200.0  # 100s later — past the 60s window
        assert inmemory_rate_check("k", limit=3, window=60) is True
