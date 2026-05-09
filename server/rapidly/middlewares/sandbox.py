"""Sandbox indicator middleware.

Tags every HTTP response with ``X-Rapidly-Sandbox: 1`` so downstream
consumers (browser DevTools, test harnesses) can detect the sandbox
environment.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_HEADER_NAME: str = "X-Rapidly-Sandbox"
_HEADER_VALUE: str = "1"


class SandboxHeaderMiddleware:
    """Inject the sandbox indicator header into every HTTP response."""

    __slots__ = ("_app",)

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        async def _inject(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                MutableHeaders(scope=message)[_HEADER_NAME] = _HEADER_VALUE
            await send(message)

        await self._app(scope, receive, _inject)
