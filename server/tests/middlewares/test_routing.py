"""Tests for ``rapidly/middlewares/routing.py::RouteNormalizationMiddleware``.

Legacy-path rewriter + deprecation-header injector. Regressions here
either break paying integrations using the legacy ``/v1`` prefix or
silently stop warning them about the upcoming cutover.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

import pytest
from starlette.types import Message, Receive, Scope, Send

from rapidly.middlewares.routing import (
    _DEPRECATION_HEADER,
    _DEPRECATION_MESSAGE,
    RouteNormalizationMiddleware,
    _RewriteRule,
)


async def _noop_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


def _downstream_recording() -> tuple[
    list[Scope], Callable[[Scope, Receive, Send], Awaitable[None]]
]:
    """An ASGI app that records the scope it was called with and emits
    a single empty http.response.start/body pair."""
    scopes: list[Scope] = []

    async def _app(scope: Scope, receive: Receive, send: Send) -> None:
        scopes.append(scope)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    return scopes, _app


def _capture_send() -> tuple[list[Message], Send]:
    captured: list[Message] = []

    async def _send(msg: Message) -> None:
        captured.append(msg)

    return captured, _send


# ── _RewriteRule ──


class TestRewriteRule:
    def test_apply_rewrites_matching_prefix(self) -> None:
        rule = _RewriteRule.compile(r"^/v1/", "/api/")
        new, rewritten = rule.apply("/v1/users")
        assert new == "/api/users"
        assert rewritten is True

    def test_apply_leaves_non_matching_path_unchanged(self) -> None:
        rule = _RewriteRule.compile(r"^/v1/", "/api/")
        new, rewritten = rule.apply("/other/path")
        assert new == "/other/path"
        assert rewritten is False

    def test_apply_reports_rewritten_false_when_subn_count_is_zero(
        self,
    ) -> None:
        # The implementation keys on ``n > 0`` from re.subn — pinning
        # that the boolean reflects the match count, not just string
        # equality.
        rule = _RewriteRule.compile(r"^/nothing/", "/also-nothing/")
        _, rewritten = rule.apply("/v1/users")
        assert rewritten is False

    def test_compile_accepts_pre_compiled_pattern(self) -> None:
        import re

        pat = re.compile(r"^/v1/")
        rule = _RewriteRule.compile(pat, "/api/")
        new, _ = rule.apply("/v1/x")
        assert new == "/api/x"


# ── RouteNormalizationMiddleware ──


@pytest.mark.asyncio
class TestRouteNormalizationMiddleware:
    async def test_rewrites_matching_path_before_dispatch(self) -> None:
        scopes, downstream = _downstream_recording()
        mw = RouteNormalizationMiddleware(downstream, r"^/v1/", "/api/")
        _, send = _capture_send()

        await mw(
            cast(Scope, {"type": "http", "path": "/v1/users"}),
            _noop_receive,
            send,
        )

        # Downstream saw the REWRITTEN path — not the legacy one.
        assert scopes[0]["path"] == "/api/users"

    async def test_injects_deprecation_header_on_rewritten_responses(
        self,
    ) -> None:
        _, downstream = _downstream_recording()
        mw = RouteNormalizationMiddleware(downstream, r"^/v1/", "/api/")
        captured, send = _capture_send()

        await mw(
            cast(Scope, {"type": "http", "path": "/v1/users"}),
            _noop_receive,
            send,
        )

        headers = {
            k.decode(): v.decode()
            for k, v in cast(list[tuple[bytes, bytes]], captured[0]["headers"])
        }
        assert headers[_DEPRECATION_HEADER.lower()] == _DEPRECATION_MESSAGE

    async def test_does_not_tag_requests_that_were_not_rewritten(self) -> None:
        _, downstream = _downstream_recording()
        mw = RouteNormalizationMiddleware(downstream, r"^/v1/", "/api/")
        captured, send = _capture_send()

        await mw(
            cast(Scope, {"type": "http", "path": "/api/users"}),
            _noop_receive,
            send,
        )

        headers = {
            k.decode(): v.decode()
            for k, v in cast(list[tuple[bytes, bytes]], captured[0]["headers"])
        }
        # Already-modern paths must NOT get the deprecation header —
        # otherwise we'd be telling users to update code they already
        # updated.
        assert _DEPRECATION_HEADER.lower() not in headers

    async def test_passes_through_lifespan_scopes(self) -> None:
        # Lifespan events don't have a ``path``; rewriting would
        # KeyError. Pin the scope-type guard.
        sent: list[Message] = []

        async def _lifespan_app(scope: Scope, receive: Receive, send: Send) -> None:
            await send({"type": "lifespan.startup.complete"})

        async def _send(msg: Message) -> None:
            sent.append(msg)

        mw = RouteNormalizationMiddleware(_lifespan_app, r"^/v1/", "/api/")
        await mw(cast(Scope, {"type": "lifespan"}), _noop_receive, _send)
        assert sent == [{"type": "lifespan.startup.complete"}]

    async def test_handles_websocket_scopes(self) -> None:
        # Module lists ``websocket`` in its guarded scope types.
        scopes, downstream = _downstream_recording()
        mw = RouteNormalizationMiddleware(downstream, r"^/v1/", "/api/")
        _, send = _capture_send()

        await mw(
            cast(Scope, {"type": "websocket", "path": "/v1/socket"}),
            _noop_receive,
            send,
        )

        assert scopes[0]["path"] == "/api/socket"

    async def test_deprecation_message_names_the_cutover(self) -> None:
        # Pinning the specific text so operators searching logs /
        # grepping headers find a consistent phrase.
        assert "/v1" in _DEPRECATION_MESSAGE
        assert "/api" in _DEPRECATION_MESSAGE

    async def test_deprecation_header_name_is_stable(self) -> None:
        assert _DEPRECATION_HEADER == "X-Rapidly-Deprecation-Notice"
