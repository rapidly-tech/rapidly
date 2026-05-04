"""Tests for ``rapidly/middlewares/sandbox.py::SandboxHeaderMiddleware``.

The middleware tags every HTTP + WebSocket response with
``X-Rapidly-Sandbox: 1`` so downstream consumers can detect the
sandbox environment. Non-HTTP scopes (``lifespan``) must pass through
unchanged — tagging a lifespan event would crash the ASGI server.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

import pytest
from starlette.types import Message, Receive, Scope, Send

from rapidly.middlewares.sandbox import SandboxHeaderMiddleware


async def _noop_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


def _make_downstream_app(
    response_headers: list[tuple[bytes, bytes]],
) -> Callable[[Scope, Receive, Send], Awaitable[None]]:
    """A minimal ASGI app that emits a single ``http.response.start`` with
    the supplied headers, then a body, then completes."""

    async def _app(scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": response_headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"ok",
                "more_body": False,
            }
        )

    return _app


def _capture_send() -> tuple[list[Message], Send]:
    """Return a (messages, send) pair where ``send`` appends each
    message to the list."""
    captured: list[Message] = []

    async def _send(msg: Message) -> None:
        captured.append(msg)

    return captured, _send


@pytest.mark.asyncio
class TestSandboxHeaderMiddleware:
    async def test_injects_header_on_http_response(self) -> None:
        downstream = _make_downstream_app([])
        mw = SandboxHeaderMiddleware(downstream)
        captured, send = _capture_send()

        await mw(cast(Scope, {"type": "http", "headers": []}), _noop_receive, send)

        start = captured[0]
        headers = {
            k.decode(): v.decode()
            for k, v in cast(list[tuple[bytes, bytes]], start["headers"])
        }
        assert headers["x-rapidly-sandbox"] == "1"

    async def test_preserves_existing_response_headers(self) -> None:
        # Downstream sets a Content-Type; middleware must add (not
        # replace) the sandbox header.
        downstream = _make_downstream_app([(b"content-type", b"application/json")])
        mw = SandboxHeaderMiddleware(downstream)
        captured, send = _capture_send()

        await mw(cast(Scope, {"type": "http", "headers": []}), _noop_receive, send)

        headers = {
            k.decode(): v.decode()
            for k, v in cast(list[tuple[bytes, bytes]], captured[0]["headers"])
        }
        assert headers["x-rapidly-sandbox"] == "1"
        assert headers["content-type"] == "application/json"

    async def test_injects_on_websocket_start_messages(self) -> None:
        # WebSocket scopes also get the header (the module lists
        # ``websocket`` in the tagged scope types). Drive a minimal
        # downstream that emits the ``http.response.start``-shaped
        # message the middleware targets.
        downstream = _make_downstream_app([])
        mw = SandboxHeaderMiddleware(downstream)
        captured, send = _capture_send()

        await mw(
            cast(Scope, {"type": "websocket", "headers": []}),
            _noop_receive,
            send,
        )

        headers = {
            k.decode(): v.decode()
            for k, v in cast(list[tuple[bytes, bytes]], captured[0]["headers"])
        }
        assert headers["x-rapidly-sandbox"] == "1"

    async def test_passes_through_lifespan_without_touching_messages(
        self,
    ) -> None:
        # Lifespan events (``lifespan.startup.complete`` etc.) don't
        # have a ``headers`` field; the middleware must pass them
        # through unchanged.
        lifespan_messages: list[Message] = [
            {"type": "lifespan.startup.complete"},
        ]
        seen: list[Message] = []

        async def _lifespan_app(scope: Scope, receive: Receive, send: Send) -> None:
            for m in lifespan_messages:
                await send(m)

        async def _send(msg: Message) -> None:
            seen.append(msg)

        mw = SandboxHeaderMiddleware(_lifespan_app)
        await mw(cast(Scope, {"type": "lifespan"}), _noop_receive, _send)

        # Lifespan messages pass through verbatim — no header injection.
        assert seen == lifespan_messages

    async def test_passes_through_non_start_messages_without_modification(
        self,
    ) -> None:
        # Body messages (``http.response.body``) don't get headers —
        # the middleware only mutates the ``http.response.start`` frame.
        downstream = _make_downstream_app([])
        mw = SandboxHeaderMiddleware(downstream)
        captured, send = _capture_send()

        await mw(cast(Scope, {"type": "http", "headers": []}), _noop_receive, send)

        # Body message (second) is unmodified.
        body = captured[1]
        assert body["type"] == "http.response.body"
        assert "headers" not in body
        assert body["body"] == b"ok"

    async def test_header_constants_match_documented_values(self) -> None:
        from rapidly.middlewares.sandbox import _HEADER_NAME, _HEADER_VALUE

        # Pinning explicit strings — clients (browser DevTools, test
        # harnesses, alerting) key on these values.
        assert _HEADER_NAME == "X-Rapidly-Sandbox"
        assert _HEADER_VALUE == "1"
