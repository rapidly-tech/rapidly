"""ASGI middleware that feeds Prometheus counters and histograms for HTTP traffic.

Hooks into the ASGI send channel to capture the response status code,
then records request count + duration after the downstream app finishes.
Paths on the deny-list (health probes, JWKS, etc.) and apps registered
in ``METRICS_EXCLUDED_APPS`` are silently skipped to keep label
cardinality manageable.
"""

from __future__ import annotations

import time
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rapidly.observability.http_metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUEST_TOTAL,
    METRICS_DENY_LIST,
    METRICS_EXCLUDED_APPS,
)

# Freeze the deny-list into a frozenset once at import time so that
# membership checks inside the hot path are O(1).
_BLOCKED_PATHS: Final[frozenset[str]] = frozenset(METRICS_DENY_LIST)

_FALLBACK_STATUS: Final[str] = "500"
_FALLBACK_METHOD: Final[str] = "UNKNOWN"


def _path_template_for(scope: Scope) -> str | None:
    """Derive a low-cardinality route template from the ASGI scope.

    Returns ``None`` when metrics should *not* be recorded — either
    because the path is deny-listed, the app is excluded, or no route
    was matched (which would cause cardinality explosion from bots).
    """
    # Skip excluded sub-applications (e.g. the admin panel).
    scope_app = scope.get("app")
    if scope_app is not None and scope_app in METRICS_EXCLUDED_APPS:
        return None

    raw_path: str = scope.get("path", "")

    # Exact match or prefix match against the deny-list.
    if raw_path in _BLOCKED_PATHS:
        return None
    for prefix in _BLOCKED_PATHS:
        if raw_path.startswith(prefix):
            return None

    # After routing, FastAPI attaches the matched Route object.
    route = scope.get("route")
    if route is not None and hasattr(route, "path"):
        return route.path

    # No matched route — likely a 404 from scanners / bots.
    return None


class RequestMetricsMiddleware:
    """Thin ASGI middleware that records per-request Prometheus metrics."""

    __slots__ = ("_app",)

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        captured_status = _FALLBACK_STATUS
        clock_start = time.perf_counter()

        async def _intercept(message: Message) -> None:
            nonlocal captured_status
            if message["type"] == "http.response.start":
                captured_status = str(message["status"])
            await send(message)

        try:
            await self._app(scope, receive, _intercept)
        finally:
            template = _path_template_for(scope)
            if template is not None:
                elapsed_seconds = time.perf_counter() - clock_start
                http_method = scope.get("method", _FALLBACK_METHOD)
                HTTP_REQUEST_TOTAL.labels(
                    endpoint=template,
                    method=http_method,
                    status_code=captured_status,
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(
                    endpoint=template,
                    method=http_method,
                ).observe(elapsed_seconds)
