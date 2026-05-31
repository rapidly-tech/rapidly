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
    _is_trusted_proxy,
    check_otp_rate_limit,
    inmemory_rate_check,
    resolve_client_ip,
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


# ── Client IP resolution (X-Forwarded-For aware) ──


def _make_resolver_request(
    *, xff: str | None = None, peer: str | None = "8.8.8.8"
) -> Any:
    """Build a minimal FastAPI Request-shaped mock for the
    resolver. Only ``.headers`` and ``.client.host`` are read."""
    req = MagicMock()
    req.headers = {"X-Forwarded-For": xff} if xff else {}
    if peer is None:
        req.client = None
    else:
        req.client = MagicMock()
        req.client.host = peer
    return req


class TestIsTrustedProxy:
    """Trust model: RFC 1918 + loopback + link-local + ULA.
    Anything else (public IPs, malformed strings) is untrusted.
    """

    def test_rfc1918_ipv4_ranges_trusted(self) -> None:
        # 10/8, 172.16/12, 192.168/16 — the three classic
        # private ranges where load balancers / sidecars live.
        for ip in ("10.0.0.5", "172.16.5.5", "192.168.1.1"):
            assert _is_trusted_proxy(ip), f"{ip} should be trusted"

    def test_loopback_trusted(self) -> None:
        # Localhost reverse proxies, k8s pod-local sidecars.
        assert _is_trusted_proxy("127.0.0.1")
        assert _is_trusted_proxy("::1")

    def test_link_local_trusted(self) -> None:
        # 169.254/16 — includes AWS/GCP metadata service IP,
        # but a proxy chain reaching this address would be
        # a deployment bug regardless. Trusted as a proxy
        # for consistency with private-range behaviour.
        assert _is_trusted_proxy("169.254.10.5")

    def test_ipv6_ula_trusted(self) -> None:
        # fc00::/7 — IPv6 Unique Local Addresses, the
        # equivalent of RFC 1918.
        assert _is_trusted_proxy("fc00::1")
        assert _is_trusted_proxy("fd12:3456:789a::1")

    def test_public_ipv4_untrusted(self) -> None:
        # Real internet addresses — could be the actual client
        # OR a spoofed XFF entry; either way NOT a proxy.
        for ip in ("8.8.8.8", "1.1.1.1", "9.9.9.9"):
            assert not _is_trusted_proxy(ip), f"{ip} should be untrusted"

    def test_public_ipv6_untrusted(self) -> None:
        # Global unicast.
        # 2606:4700:4700::1111 is Cloudflare DNS; 2001:db8::/32 is
        # RFC 3849 documentation prefix and Python treats it private.
        assert not _is_trusted_proxy("2606:4700:4700::1111")

    def test_malformed_string_untrusted(self) -> None:
        # Defensive: a malformed XFF entry shouldn't crash the
        # resolver. Return False so we don't accidentally trust
        # garbage as a proxy.
        assert not _is_trusted_proxy("not-an-ip")
        assert not _is_trusted_proxy("")
        assert not _is_trusted_proxy("999.999.999.999")


class TestResolveClientIP:
    """The resolver walks XFF right-to-left, peeling trusted
    proxies, returning the first untrusted entry. Falls back to
    request.client.host if no XFF or all entries trusted.

    Trust model assumption: each proxy in the chain APPENDS its
    own observation to XFF, so the RIGHTMOST entry is always the
    nearest trusted hop. We never trust the rightmost as the
    client; the FIRST untrusted entry walking back is the real
    client.
    """

    def test_no_xff_returns_peer_host(self) -> None:
        # Direct hit: no proxy, use the socket-level peer.
        req = _make_resolver_request(xff=None, peer="8.8.8.8")
        assert resolve_client_ip(req) == "8.8.8.8"

    def test_no_xff_no_peer_returns_unknown(self) -> None:
        # Stable rate-limit key even when both signals are
        # missing — callers should never have to None-check.
        req = _make_resolver_request(xff=None, peer=None)
        assert resolve_client_ip(req) == "unknown"

    def test_single_trusted_proxy_returns_xff_client(self) -> None:
        # Single LB in front: XFF = "<real client>"; peer is
        # the LB's private IP. Walk right-to-left, skip nothing
        # since the only entry is the public client.
        req = _make_resolver_request(xff="8.8.8.8", peer="10.0.0.5")
        assert resolve_client_ip(req) == "8.8.8.8"

    def test_chain_of_trusted_proxies_walks_through(self) -> None:
        # Layered proxies (e.g. CDN → LB → app). Each appends
        # to XFF. Walking right-to-left peels the proxies until
        # the original client surfaces.
        req = _make_resolver_request(
            xff="8.8.8.8, 10.0.0.5, 172.16.0.10",
            peer="192.168.1.1",
        )
        assert resolve_client_ip(req) == "8.8.8.8"

    def test_spoofed_xff_with_attacker_in_left_position(self) -> None:
        # CRITICAL SECURITY PIN: an attacker can put anything in
        # XFF, including making themselves look like a proxy.
        # The trust model defends because we walk RIGHT-to-LEFT
        # — the rightmost entry is the trusted proxy's
        # observation, which is the REAL public client.
        #
        # Setup: attacker forges ``"victim, 10.0.0.5"`` thinking
        # they can pin the rate-limit to "victim". The reverse
        # proxy APPENDS its observation of the attacker's actual
        # public IP, making the chain ``"victim, 10.0.0.5,
        # <attacker_real_ip>"``. We walk right-to-left, skip the
        # private 10.0.0.5, and return the attacker's real IP —
        # NOT "victim".
        req = _make_resolver_request(
            xff="victim@example.com-spoof, 10.0.0.5, 1.1.1.1",
            peer="192.168.1.1",
        )
        assert resolve_client_ip(req) == "1.1.1.1"

    def test_all_trusted_chain_falls_back_to_peer(self) -> None:
        # Service-mesh-internal traffic: every chain entry is a
        # private-range proxy. There's no public client. Fall
        # back to peer (also private, but at least real).
        req = _make_resolver_request(xff="10.0.0.1, 10.0.0.2", peer="10.0.0.3")
        assert resolve_client_ip(req) == "10.0.0.3"

    def test_whitespace_in_xff_trimmed(self) -> None:
        # XFF spec allows whitespace after commas; the standard
        # convention is "ip, ip, ip" but real headers may have
        # "ip,ip" or "ip,  ip". Both must parse.
        req = _make_resolver_request(
            xff="  8.8.8.8  ,  10.0.0.5  ", peer="10.0.0.5"
        )
        assert resolve_client_ip(req) == "8.8.8.8"

    def test_empty_xff_entries_skipped(self) -> None:
        # Edge case: trailing/leading commas or double commas
        # produce empty strings after split. Must skip without
        # treating them as "untrusted" (which would return "").
        req = _make_resolver_request(xff=",, 8.8.8.8,, 10.0.0.5,", peer="10.0.0.5")
        assert resolve_client_ip(req) == "8.8.8.8"

    def test_malformed_xff_entry_skipped(self) -> None:
        # An XFF entry that isn't a valid IP gets treated as
        # untrusted (could be a Forwarded= prefix mistake or
        # header smuggling). Walking right-to-left: skip the
        # trusted proxy, hit the malformed entry — return it
        # as the "client" rather than crash. Defensive default.
        req = _make_resolver_request(
            xff="not-an-ip, 10.0.0.5",
            peer="192.168.1.1",
        )
        assert resolve_client_ip(req) == "not-an-ip"
