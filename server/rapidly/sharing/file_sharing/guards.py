"""HTTP-layer guards for file sharing endpoints.

Centralises body-size checks, slug validation, bearer-token extraction,
and application-level rate limiting so that ``api.py`` stays thin.
"""

import re

import structlog
from fastapi import HTTPException, Request, WebSocket
from redis import RedisError

from rapidly.redis import Redis

from .redis_scripts import ATOMIC_INCR_EXPIRE_LUA
from .utils import hash_ip

_log = structlog.get_logger(__name__)


# ── Body size ────────────────────────────────────────────────────────────

# Maximum request body size for secret/file creation (defense-in-depth).
# Pydantic validates max_length on the message field, but this check
# rejects oversized payloads before the full body is parsed into JSON,
# reducing memory pressure from malicious large requests.
MAX_SECRET_BODY_SIZE = 2 * 1024 * 1024  # 2MB (1MB payload + JSON overhead)


async def check_body_size(
    http_request: Request, max_size: int = MAX_SECRET_BODY_SIZE
) -> None:
    """Reject requests with Content-Length exceeding the limit.

    Also reads the actual body to enforce the limit when Content-Length
    is missing (e.g. chunked transfer encoding).
    """
    content_length = http_request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"Request body too large (max {max_size} bytes)",
                )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid Content-Length header",
            )
    else:
        # No Content-Length header (chunked encoding) — read body and check size
        body = await http_request.body()
        if len(body) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Request body too large (max {max_size} bytes)",
            )


# ── WebSocket Redis helper ───────────────────────────────────────────────


async def get_redis_ws(ws: WebSocket) -> Redis:
    """Get Redis from WebSocket state (WebSocket endpoints can't use get_redis)."""
    return ws.state.redis


# ── Bearer token extraction ──────────────────────────────────────────────


def extract_bearer_token(authorization: str | None) -> str | None:
    """Extract the token from a 'Bearer <token>' Authorization header."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


# ── Slug validation ──────────────────────────────────────────────────────

# Only lowercase alphanumeric, hyphens, and forward slashes (for long slugs)
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9/\-]{1,255}$")


def validate_slug(slug: str) -> str:
    """Validate a channel slug from path parameters.

    Prevents Redis key injection via crafted slugs containing
    special characters, path traversal sequences, or excessive length.
    """
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")
    if ".." in slug:
        raise HTTPException(status_code=400, detail="Invalid slug format")
    return slug


# ── Application-level rate limiting (defense-in-depth) ───────────────────
# These limits complement the WebSocket rate limits in signaling.py.
# HTTP endpoints use per-action limits below; WebSocket signaling uses
# per-IP connection rate (WS_CONN_RATE_LIMIT) and per-connection message
# rate (WS_MSG_RATE_LIMIT). Both layers are intentional: HTTP limits
# protect channel operations; WS limits protect signaling bandwidth.

# Channel creation rate limiting: max 20 channels per IP per 10 minutes
CHANNEL_CREATE_RATE_LIMIT = 20
CHANNEL_CREATE_RATE_WINDOW = 600  # seconds

# Channel fetch rate limiting: max 60 requests per IP per minute
CHANNEL_FETCH_RATE_LIMIT = 60
CHANNEL_FETCH_RATE_WINDOW = 60  # seconds

# Generic channel action rate limiting: max 30 requests per IP per minute
CHANNEL_ACTION_RATE_LIMIT = 30
CHANNEL_ACTION_RATE_WINDOW = 60  # seconds

# Secret/file creation rate limiting: max 30 per IP per 10 minutes
SECRET_CREATE_RATE_LIMIT = 30
SECRET_CREATE_RATE_WINDOW = 600  # seconds

# Secret/file fetch rate limiting: max 60 per IP per minute
SECRET_FETCH_RATE_LIMIT = 60
SECRET_FETCH_RATE_WINDOW = 60  # seconds

# Secret metadata (peek) rate limiting: max 30 per IP per minute
SECRET_METADATA_RATE_LIMIT = 30
SECRET_METADATA_RATE_WINDOW = 60  # seconds


async def check_rate_limit(
    http_request: Request,
    redis: Redis,
    action: str,
    limit: int,
    window: int,
    *,
    detail: str = "Too many requests. Try again later.",
) -> None:
    """Apply IP-based rate limiting for an endpoint."""
    client_ip = http_request.client.host if http_request.client else "unknown"
    ip_hash = hash_ip(client_ip)
    rate_key = f"file-sharing:rate:{action}:{ip_hash}"
    try:
        current = await redis.eval(
            ATOMIC_INCR_EXPIRE_LUA,
            1,
            rate_key,
            window,
        )
    except RedisError:
        # Redis unavailable — fail closed to prevent abuse during outages.
        # In multi-process deployments, in-memory fallback is trivially bypassed
        # by distributing requests across processes.
        _log.warning(
            "Rate limit Redis unavailable for %s — rejecting request (fail-closed)",
            action,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Rate limit service unavailable. Please try again shortly.",
        )
    if int(current) > limit:
        raise HTTPException(status_code=429, detail=detail)
