"""Shared rate limiting utilities.

Provides Redis-backed OTP rate limiting with in-memory fallback,
used by login code and customer portal session endpoints.
"""

import hashlib
import hmac
import time

import structlog
from fastapi import HTTPException, Request
from redis.asyncio import Redis

from rapidly.config import settings

_log = structlog.get_logger(__name__)

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
    client_ip = request.client.host if request.client else "unknown"
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
