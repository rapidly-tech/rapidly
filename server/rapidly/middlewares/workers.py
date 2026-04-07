"""Background-job flush middleware.

Opens a ``JobQueueManager`` context around each request so that any jobs
enqueued during request handling are flushed to the Dramatiq broker
atomically when the request completes.
"""

from __future__ import annotations

import dramatiq
from starlette.types import ASGIApp, Receive, Scope, Send

from rapidly.worker import JobQueueManager


class JobDispatchMiddleware:
    """Ensure enqueued jobs are flushed to the broker after each request."""

    __slots__ = ("_app",)

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        broker = dramatiq.get_broker()
        redis = scope["state"]["redis"]
        async with JobQueueManager.open(broker, redis):
            await self._app(scope, receive, send)
