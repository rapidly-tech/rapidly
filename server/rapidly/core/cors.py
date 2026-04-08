"""Two-tier CORS middleware: credentialed dashboard vs. public API.

The ``CORSMatcherMiddleware`` evaluates each incoming ``Origin`` header
against an ordered list of ``CORSConfig`` rules.  The first rule whose
``matcher`` returns ``True`` wins, and its pre-built ``CORSMiddleware``
handles the preflight or simple response.  If no rule matches the origin
is ignored (no CORS headers are added).

Architecture
------------
``CORSConfig`` is a frozen dataclass that encapsulates the Starlette
``CORSMiddleware`` kwargs *plus* a callable matcher.  The middleware
pre-builds each ``CORSMiddleware`` instance at init time so there is
zero per-request allocation cost.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

# Preflight cache duration: 10 minutes.
_PREFLIGHT_MAX_AGE: int = 600


# ---------------------------------------------------------------------------
# Matcher protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class CORSMatcher(Protocol):
    """Callable that decides whether a given origin matches a CORS rule."""

    def __call__(self, origin: str, scope: Scope) -> bool: ...


# ---------------------------------------------------------------------------
# Rule dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class CORSConfig:
    """Immutable description of a CORS policy bound to an origin matcher."""

    matcher: CORSMatcher
    allow_origins: Sequence[str] = ()
    allow_methods: Sequence[str] = ("GET",)
    allow_headers: Sequence[str] = ()
    allow_credentials: bool = False
    allow_origin_regex: str | None = None
    expose_headers: Sequence[str] = ()
    max_age: int = _PREFLIGHT_MAX_AGE

    def build_middleware(self, app: ASGIApp) -> CORSMiddleware:
        """Materialise a ``CORSMiddleware`` using the settings in this config."""
        return CORSMiddleware(
            app=app,
            allow_origins=self.allow_origins,
            allow_methods=self.allow_methods,
            allow_headers=self.allow_headers,
            allow_credentials=self.allow_credentials,
            allow_origin_regex=self.allow_origin_regex,
            expose_headers=self.expose_headers,
            max_age=self.max_age,
        )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class CORSMatcherMiddleware:
    """Routes CORS handling to the first ``CORSConfig`` whose matcher fires.

    Non-HTTP scopes and requests without an ``Origin`` header bypass
    CORS processing entirely.
    """

    __slots__ = ("_app", "_rules")

    def __init__(self, app: ASGIApp, *, configs: Sequence[CORSConfig]) -> None:
        self._app = app
        # Pre-build each middleware once at startup.
        self._rules: tuple[tuple[CORSConfig, CORSMiddleware], ...] = tuple(
            (cfg, cfg.build_middleware(app)) for cfg in configs
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get("origin")

        # No origin -- not a cross-origin request; skip CORS entirely.
        if origin is None:
            await self._app(scope, receive, send)
            return

        matched_mw = self._match(origin, scope)
        if matched_mw is None:
            # Origin does not match any rule -- pass through without CORS headers.
            await self._app(scope, receive, send)
            return

        # Preflight?
        if scope["method"] == "OPTIONS" and "access-control-request-method" in headers:
            response = matched_mw.preflight_response(request_headers=headers)
            await response(scope, receive, send)
            return

        # Simple / actual request.
        await matched_mw.simple_response(scope, receive, send, request_headers=headers)

    # -- internal ----------------------------------------------------------

    def _match(self, origin: str, scope: Scope) -> CORSMiddleware | None:
        """Return the first matching ``CORSMiddleware`` or ``None``."""
        for cfg, mw in self._rules:
            if cfg.matcher(origin, scope):
                return mw
        return None


__all__ = ["CORSConfig", "CORSMatcherMiddleware", "Scope"]
