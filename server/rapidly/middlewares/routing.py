"""Legacy API-path rewriting with deprecation notice.

Rewrites request paths that match a user-supplied regex and injects a
deprecation header so clients know to update their integration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rapidly.logging import Logger

_log: Logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class _RewriteRule:
    """A compiled rewrite pattern and its replacement string."""

    pattern: re.Pattern[str]
    replacement: str

    @classmethod
    def compile(cls, pattern: str | re.Pattern[str], replacement: str) -> _RewriteRule:
        compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
        return cls(pattern=compiled, replacement=replacement)

    def apply(self, path: str) -> tuple[str, bool]:
        """Return ``(new_path, was_rewritten)``."""
        new_path, n = self.pattern.subn(self.replacement, path)
        return new_path, n > 0


# Deprecation header injected when a path is rewritten.
_DEPRECATION_HEADER: str = "X-Rapidly-Deprecation-Notice"
_DEPRECATION_MESSAGE: str = (
    "The API root has moved from /v1 to /api. Please update your integration."
)


class RouteNormalizationMiddleware:
    """Rewrite legacy API paths and inject a deprecation header."""

    __slots__ = ("_app", "_rule")

    def __init__(
        self, app: ASGIApp, pattern: str | re.Pattern[str], replacement: str
    ) -> None:
        self._app = app
        self._rule = _RewriteRule.compile(pattern, replacement)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        new_path, rewritten = self._rule.apply(scope["path"])
        scope["path"] = new_path

        if rewritten:
            _log.warning(
                "route.rewritten",
                pattern=self._rule.pattern.pattern,
                replacement=self._rule.replacement,
                path=new_path,
            )

        async def _maybe_tag(message: Message) -> None:
            if message["type"] == "http.response.start" and rewritten:
                message.setdefault("headers", [])
                MutableHeaders(scope=message)[_DEPRECATION_HEADER] = (
                    _DEPRECATION_MESSAGE
                )
            await send(message)

        await self._app(scope, receive, _maybe_tag)
