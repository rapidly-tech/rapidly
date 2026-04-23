"""Tests for ``rapidly/core/cors.py``.

The ``CORSMatcherMiddleware`` is the two-tier CORS router that decides
which policy (credentialed-dashboard vs public-API) applies to each
cross-origin request. A mismatched rule ordering or a wrong matcher
evaluation is a direct XSRF / credential-leak class of bug.

Exercised with a hand-rolled ASGI harness so the tests don't need a
TestClient or a live FastAPI app — the middleware is pure ASGI and
documented to be called directly.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import pytest
from starlette.types import Message, Receive, Scope, Send

from rapidly.core.cors import CORSConfig, CORSMatcherMiddleware

# ── ASGI harness ──


def _http_scope(
    *,
    method: str = "GET",
    origin: str | None = "https://dashboard.example.test",
    extra_headers: Sequence[tuple[bytes, bytes]] = (),
) -> Scope:
    headers: list[tuple[bytes, bytes]] = []
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    headers.extend(extra_headers)
    return {
        "type": "http",
        "method": method,
        "scheme": "https",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "server": ("testserver", 443),
        "client": ("127.0.0.1", 0),
    }


def _make_sink() -> tuple[list[str], Callable[[Scope, Receive, Send], Awaitable[None]]]:
    calls: list[str] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        calls.append(scope["type"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    return calls, downstream


def _capture_send() -> tuple[list[Message], Send]:
    messages: list[Message] = []

    async def send(msg: Message) -> None:
        messages.append(msg)

    return messages, send


async def _noop_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


# ── Tests ──


class TestCORSConfigFrozenDataclass:
    def test_is_frozen(self) -> None:
        # Accidentally mutating a config at runtime would let a
        # request-time code path relax ``allow_credentials`` — the
        # frozen+slots pair raises FrozenInstanceError on assignment.
        import dataclasses

        cfg = CORSConfig(matcher=lambda origin, scope: True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.allow_credentials = True  # type: ignore[misc]

    def test_defaults_are_restrictive(self) -> None:
        # Defensive: if a caller forgets to set a policy explicitly,
        # the safe default is GET-only, no credentials, no allowed
        # origins. An accidentally-permissive default would silently
        # open up every endpoint.
        cfg = CORSConfig(matcher=lambda origin, scope: True)
        assert cfg.allow_origins == ()
        assert cfg.allow_methods == ("GET",)
        assert cfg.allow_headers == ()
        assert cfg.allow_credentials is False
        assert cfg.expose_headers == ()
        assert cfg.max_age == 600


@pytest.mark.asyncio
class TestCORSMatcherMiddleware:
    async def test_passes_non_http_scopes_through_untouched(self) -> None:
        calls, downstream = _make_sink()
        mw = CORSMatcherMiddleware(downstream, configs=[])
        _, send = _capture_send()
        await mw({"type": "websocket", "path": "/"}, _noop_receive, send)
        assert calls == ["websocket"]

    async def test_passes_requests_without_origin_through_untouched(self) -> None:
        # No Origin header = not a cross-origin request; CORS must
        # not add any headers.
        calls, downstream = _make_sink()
        mw = CORSMatcherMiddleware(
            downstream,
            configs=[
                CORSConfig(
                    matcher=lambda origin, scope: True,
                    allow_origins=["*"],
                ),
            ],
        )
        msgs, send = _capture_send()
        await mw(_http_scope(origin=None), _noop_receive, send)
        assert calls == ["http"]
        # No CORS headers injected.
        start = next(m for m in msgs if m["type"] == "http.response.start")
        header_names = {k.lower() for k, _ in start["headers"]}
        assert not any(h.startswith(b"access-control-") for h in header_names)

    async def test_origin_not_matched_by_any_rule_gets_no_cors_headers(
        self,
    ) -> None:
        # Silently ignoring a non-matching origin is the documented
        # behaviour — denying with 403 would break public assets.
        calls, downstream = _make_sink()
        mw = CORSMatcherMiddleware(
            downstream,
            configs=[
                CORSConfig(
                    matcher=lambda origin, scope: origin == "https://allowed.test",
                    allow_origins=["https://allowed.test"],
                ),
            ],
        )
        msgs, send = _capture_send()
        await mw(_http_scope(origin="https://attacker.test"), _noop_receive, send)
        assert calls == ["http"]
        start = next(m for m in msgs if m["type"] == "http.response.start")
        for k, _ in start["headers"]:
            assert not k.lower().startswith(b"access-control-")

    async def test_first_matching_rule_wins(self) -> None:
        # Rule order is load-bearing: the dashboard (credentialed)
        # rule comes before the public-API rule so a dashboard
        # origin does NOT get the weaker public-API policy.
        tracker: list[str] = []

        def m_first(origin: str, scope: Any) -> bool:
            tracker.append("first")
            return origin == "https://dashboard.example.test"

        def m_second(origin: str, scope: Any) -> bool:
            tracker.append("second")
            return True  # wildcard

        _calls, downstream = _make_sink()
        mw = CORSMatcherMiddleware(
            downstream,
            configs=[
                CORSConfig(
                    matcher=m_first,
                    allow_origins=["https://dashboard.example.test"],
                    allow_credentials=True,
                ),
                CORSConfig(matcher=m_second, allow_origins=["*"]),
            ],
        )
        _, send = _capture_send()
        await mw(_http_scope(), _noop_receive, send)
        # Only the first matcher should have been evaluated.
        assert tracker == ["first"]

    async def test_preflight_requires_access_control_request_method(self) -> None:
        # A bare OPTIONS (e.g., health probe) is NOT a preflight — it
        # must fall through to ``simple_response``. Treating every
        # OPTIONS as a preflight would mean CORS headers get returned
        # for requests that shouldn't advertise policy.
        _, downstream = _make_sink()
        mw = CORSMatcherMiddleware(
            downstream,
            configs=[
                CORSConfig(
                    matcher=lambda origin, scope: True,
                    allow_origins=["https://dashboard.example.test"],
                    allow_methods=["GET", "POST"],
                ),
            ],
        )
        msgs, send = _capture_send()
        await mw(_http_scope(method="OPTIONS"), _noop_receive, send)
        # Downstream app was called (simple_response path); preflight
        # would have short-circuited with a 200 and no body from the
        # matched middleware itself.
        statuses = [m["status"] for m in msgs if m["type"] == "http.response.start"]
        assert statuses == [200]

    async def test_preflight_short_circuits_when_access_control_header_present(
        self,
    ) -> None:
        # OPTIONS + access-control-request-method = real preflight;
        # middleware must answer directly, not hit the app.
        sink_calls, downstream = _make_sink()
        mw = CORSMatcherMiddleware(
            downstream,
            configs=[
                CORSConfig(
                    matcher=lambda origin, scope: True,
                    allow_origins=["https://dashboard.example.test"],
                    allow_methods=["GET", "POST"],
                    allow_headers=["content-type"],
                ),
            ],
        )
        msgs, send = _capture_send()
        await mw(
            _http_scope(
                method="OPTIONS",
                extra_headers=[
                    (b"access-control-request-method", b"POST"),
                    (b"access-control-request-headers", b"content-type"),
                ],
            ),
            _noop_receive,
            send,
        )
        # Downstream MUST NOT be called — preflight is answered by
        # the Starlette ``CORSMiddleware.preflight_response`` helper.
        assert sink_calls == []
        # Response must include the standard preflight headers.
        start = next(m for m in msgs if m["type"] == "http.response.start")
        header_names = {k.lower() for k, _ in start["headers"]}
        assert b"access-control-allow-origin" in header_names
        assert b"access-control-allow-methods" in header_names
