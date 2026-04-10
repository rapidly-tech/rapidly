"""Per-request envelope: correlation IDs, security headers, and rate-limit placeholders.

Every HTTP request is assigned a unique correlation ID that is bound to
structlog context vars (for structured logging) and echoed back in the
``X-Request-ID`` response header.  Security-hardening and rate-limit
placeholder headers are injected via a composable header-builder pipeline.
"""

from __future__ import annotations

from collections.abc import Callable

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rapidly.core.geolocation import geolocate
from rapidly.logging import Logger, generate_correlation_id

_log: Logger = structlog.get_logger(__name__)

# Header builder type -- each builder receives the MutableHeaders dict and
# mutates it in-place.
type _HeaderBuilder = Callable[[MutableHeaders], None]

# HSTS max-age: 1 year in seconds.
_HSTS_MAX_AGE: int = 31_536_000

# Context var keys bound per-request.
_CTX_KEYS: tuple[str, ...] = ("correlation_id", "method", "path")


# ---------------------------------------------------------------------------
# Header builder functions
# ---------------------------------------------------------------------------


def _add_security_headers(headers: MutableHeaders, *, hsts: bool) -> None:
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "DENY"
    if hsts:
        headers["Strict-Transport-Security"] = (
            f"max-age={_HSTS_MAX_AGE}; includeSubDomains; preload"
        )
    if "Cache-Control" not in headers:
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; object-src 'none'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    headers["Referrer-Policy"] = "no-referrer"
    headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )


def _add_rate_limit_stubs(headers: MutableHeaders) -> None:
    headers["X-RateLimit-Limit"] = "0"
    headers["X-RateLimit-Remaining"] = "0"
    headers["X-RateLimit-Reset"] = "0"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class RequestEnvelopeMiddleware:
    """Combine correlation-ID tracking, security headers, and rate-limit
    placeholders in a single ASGI middleware.

    Parameters
    ----------
    app:
        The next ASGI application in the stack.
    enable_hsts:
        Whether to inject a Strict-Transport-Security header.
    """

    __slots__ = ("_app", "_hsts")

    def __init__(self, app: ASGIApp, *, enable_hsts: bool = True) -> None:
        self._app = app
        self._hsts = enable_hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self._app(scope, receive, send)

        cid = generate_correlation_id()

        # Resolve client IP and attach geolocation data to scope
        client = scope.get("client")
        client_ip = client[0] if client else None
        if client_ip:
            geo = geolocate(client_ip)
            scope["geo"] = geo
        else:
            scope["geo"] = None

        structlog.contextvars.bind_contextvars(
            correlation_id=cid,
            method=scope["method"],
            path=scope["path"],
        )

        async def _enrich_response(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                hdrs = MutableHeaders(scope=message)
                # Correlation
                hdrs["X-Request-ID"] = cid
                # Security
                _add_security_headers(hdrs, hsts=self._hsts)
                # Rate-limit placeholders
                _add_rate_limit_stubs(hdrs)
            await send(message)

        try:
            await self._app(scope, receive, _enrich_response)
        finally:
            structlog.contextvars.unbind_contextvars(*_CTX_KEYS)
