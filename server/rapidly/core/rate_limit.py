"""Shared rate limiting utilities.

Provides Redis-backed OTP rate limiting with in-memory fallback,
used by login code and customer portal session endpoints.
"""

import hashlib
import hmac
import ipaddress
import time

import structlog
from fastapi import HTTPException, Request
from redis.asyncio import Redis
from starlette.types import Scope

from rapidly.config import settings

_log = structlog.get_logger(__name__)


# ── Client IP resolution ──


def _is_trusted_proxy(ip_str: str) -> bool:
    """Return True if *ip_str* is a trusted reverse-proxy address.

    Trusts the standard RFC 1918 + loopback + link-local + unique-
    local ranges — these can only originate inside the deployment
    network (load balancer, sidecar proxy, ingress controller).
    A public IP in the X-Forwarded-For chain is treated as
    untrusted (could be a spoofed header from a malicious client
    that the trusted proxy faithfully forwarded).

    Returns False for unparseable strings rather than raising —
    a malformed chain element shouldn't crash the rate-limit path.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        # ip.is_private already covers RFC 1918 + ULA (fc00::/7);
        # call out is_loopback + is_link_local explicitly because
        # those are valid proxy locations too (localhost reverse
        # proxies, k8s pod-local sidecars).
    )


def resolve_client_ip(request: Request) -> str:
    """Return the originating client IP.

    Walks ``X-Forwarded-For`` RIGHT-to-LEFT, peeling off trusted
    proxies (RFC 1918 / loopback / link-local ranges), and
    returns the first untrusted address — that's the real
    client. If no XFF or all chain entries are trusted, falls
    back to ``request.client.host``.

    Trust model: an attacker on the public internet can forge
    XFF headers, but their request must traverse our trusted
    proxy chain to reach the app — the proxy will APPEND its
    own observation to XFF, so the rightmost entry is always
    the proxy and we never trust it as the client. Earlier
    entries are only trusted if they ARE proxies (private IPs).

    Returns ``"unknown"`` if everything fails so callers can
    use the result as a stable rate-limit key without None-
    checks.
    """
    # Walk the XFF chain right-to-left.
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        # XFF is comma-separated, leftmost = original client
        # (per most proxy conventions). But we walk right-to-
        # left because each proxy APPENDS its own observation,
        # so the rightmost = nearest-to-us = always trusted-
        # by-construction; the FIRST untrusted entry walking
        # back is the client.
        for raw in reversed([p.strip() for p in xff.split(",") if p.strip()]):
            if not _is_trusted_proxy(raw):
                return raw
        # All entries were trusted (chain of only-proxies, no
        # client) — extremely unusual but possible in
        # service-mesh-internal traffic. Fall through to
        # request.client.host.

    # No XFF or all-trusted chain: socket-level peer.
    if request.client:
        return request.client.host
    return "unknown"


def resolve_client_ip_from_scope(scope: Scope) -> str:
    """ASGI-Scope version of ``resolve_client_ip`` for middleware
    that runs before FastAPI wraps the scope in a ``Request``.

    The rate-limit ASGI middleware uses this to bucket anonymous
    requests by real client IP rather than by the proxy's IP
    (which previously let one attacker behind a shared XFF-only
    proxy burn the global anonymous bucket for everyone).

    Same trust model as ``resolve_client_ip``: walk
    ``X-Forwarded-For`` right-to-left, peel trusted proxies,
    return the first untrusted entry. Falls back to
    ``scope["client"][0]`` (the socket peer), then ``"unknown"``.

    Returns ``"unknown"`` if scope is malformed so callers can
    always use the result as a rate-limit key.
    """
    # ASGI scope.headers is a list of (bytes, bytes) tuples.
    xff_bytes: bytes | None = None
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            xff_bytes = value
            break
    if xff_bytes:
        try:
            xff = xff_bytes.decode("ascii")
        except UnicodeDecodeError:
            xff = ""
        if xff:
            for raw in reversed([p.strip() for p in xff.split(",") if p.strip()]):
                if not _is_trusted_proxy(raw):
                    return raw

    client = scope.get("client")
    if client and len(client) >= 1:
        return str(client[0])
    return "unknown"


# ── OTP verification rate limiting ──

OTP_VERIFY_LIMIT = 10
OTP_VERIFY_WINDOW = 900  # 15 minutes in seconds


async def check_otp_rate_limit(
    redis: Redis[str],
    request: Request,
    *,
    key_prefix: str,
) -> None:
    """Rate-limit OTP verification attempts by IP.

    Fails **closed** — if Redis is unavailable, the request is rejected
    rather than allowed through. This prevents brute-force of short OTP
    codes during Redis outages.

    Args:
        redis: Redis connection.
        request: HTTP request (used to extract client IP).
        key_prefix: Distinguishes rate limit buckets (e.g. ``"login"``, ``"portal"``).
    """
    client_ip = resolve_client_ip(request)
    ip_hash = hmac.new(
        settings.SECRET.encode(), client_ip.encode(), hashlib.sha256
    ).hexdigest()[:16]
    key = f"otp-rate:{key_prefix}:{ip_hash}"
    try:
        # Atomic INCR + EXPIRE via pipeline to prevent orphaned keys
        # if the process crashes between the two calls.
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, OTP_VERIFY_WINDOW)
            results = await pipe.execute()
        current: int = results[0]
        if current > OTP_VERIFY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Too many verification attempts. Try again later.",
            )
    except HTTPException:
        raise
    except Exception:
        _log.warning(
            "OTP rate limit check failed — rejecting request (fail-closed)",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Rate limit service unavailable. Please try again shortly.",
        )


# ── In-memory rate limiter fallback ──

_inmemory_rate_limits: dict[str, tuple[int, float]] = {}
_INMEMORY_CLEANUP_INTERVAL = 60.0  # seconds between stale-entry sweeps
_inmemory_last_cleanup = 0.0


def inmemory_rate_check(key: str, limit: int, window: int) -> bool:
    """Check and increment an in-memory rate limit counter.

    Returns True if the request is allowed, False if it should be rejected.
    Uses a simple sliding-window approach: if the window has expired, the
    counter resets. Safe without locking since the event loop is single-threaded.

    Includes periodic cleanup of expired entries to prevent unbounded growth.
    """
    global _inmemory_last_cleanup

    now = time.monotonic()
    # Periodic cleanup of expired entries
    if now - _inmemory_last_cleanup > _INMEMORY_CLEANUP_INTERVAL:
        expired_keys = [
            k
            for k, (_, start) in _inmemory_rate_limits.items()
            if now - start > max(window, 600)  # keep at least 10 min for safety
        ]
        for k in expired_keys:
            del _inmemory_rate_limits[k]
        _inmemory_last_cleanup = now

    entry = _inmemory_rate_limits.get(key)
    if entry is None or (now - entry[1]) >= window:
        # New window
        _inmemory_rate_limits[key] = (1, now)
        return True

    count, window_start = entry
    new_count = count + 1
    _inmemory_rate_limits[key] = (new_count, window_start)
    return new_count <= limit
