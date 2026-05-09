"""Tests for ``rapidly/middlewares/envelope.py``.

``RequestEnvelopeMiddleware`` owns three security-critical concerns:
- Correlation-ID tracking (``X-Request-ID`` echo + structlog context
  binding)
- Security headers (HSTS, CSP, X-Frame-Options, …)
- Rate-limit placeholder headers

Each documented header is pinned explicitly — a silent refactor that
drops ``X-Content-Type-Options: nosniff`` (for example) would expose
MIME-sniffing-based XSS on every response.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

import pytest
import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import Message, Receive, Scope, Send

from rapidly.middlewares.envelope import (
    RequestEnvelopeMiddleware,
    _add_rate_limit_stubs,
    _add_security_headers,
)


async def _noop_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


def _downstream(
    response_headers: list[tuple[bytes, bytes]] | None = None,
) -> Callable[[Scope, Receive, Send], Awaitable[None]]:
    async def _app(scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": response_headers or [],
            }
        )
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    return _app


def _capture() -> tuple[list[Message], Send]:
    msgs: list[Message] = []

    async def _send(m: Message) -> None:
        msgs.append(m)

    return msgs, _send


def _empty_headers() -> MutableHeaders:
    return MutableHeaders(
        scope={"type": "http.response.start", "status": 200, "headers": []}
    )


# ── _add_security_headers ──


class TestAddSecurityHeaders:
    def test_sets_X_Content_Type_Options_nosniff(self) -> None:
        # Blocks MIME-sniffing-based XSS in browsers.
        h = _empty_headers()
        _add_security_headers(h, hsts=False)
        assert h["x-content-type-options"] == "nosniff"

    def test_sets_X_Frame_Options_DENY(self) -> None:
        # Prevents clickjacking by rejecting iframe embedding.
        h = _empty_headers()
        _add_security_headers(h, hsts=False)
        assert h["x-frame-options"] == "DENY"

    def test_adds_HSTS_when_enabled_with_1_year_max_age(self) -> None:
        h = _empty_headers()
        _add_security_headers(h, hsts=True)
        hsts = h["strict-transport-security"]
        assert "max-age=31536000" in hsts  # 1 year in seconds
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    def test_omits_HSTS_when_disabled(self) -> None:
        h = _empty_headers()
        _add_security_headers(h, hsts=False)
        assert "strict-transport-security" not in h

    def test_default_Cache_Control_is_no_store(self) -> None:
        # Defends against sensitive-data caching by intermediaries.
        h = _empty_headers()
        _add_security_headers(h, hsts=False)
        cc = h["cache-control"]
        assert "no-store" in cc
        assert "no-cache" in cc
        assert "private" in cc

    def test_does_not_clobber_existing_Cache_Control(self) -> None:
        # The "if Cache-Control not in headers" guard lets endpoints
        # opt into their own caching rules. Pin that opt-out works.
        h = _empty_headers()
        h["Cache-Control"] = "public, max-age=600"
        _add_security_headers(h, hsts=False)
        assert h["cache-control"] == "public, max-age=600"

    def test_sets_strict_CSP(self) -> None:
        # CSP locks the app to same-origin scripts + no object/frame
        # ancestors. Pinning the directives so a silent weakening is
        # caught (default-src 'self' → 'self' data: would be a XSS
        # widening, for example).
        h = _empty_headers()
        _add_security_headers(h, hsts=False)
        csp = h["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp

    def test_sets_Referrer_Policy_no_referrer(self) -> None:
        h = _empty_headers()
        _add_security_headers(h, hsts=False)
        assert h["referrer-policy"] == "no-referrer"

    def test_sets_Permissions_Policy_denying_sensitive_apis(self) -> None:
        # Disallows camera / mic / geolocation / payment by default.
        h = _empty_headers()
        _add_security_headers(h, hsts=False)
        pp = h["permissions-policy"]
        for api in ("camera=()", "microphone=()", "geolocation=()", "payment=()"):
            assert api in pp


# ── _add_rate_limit_stubs ──


class TestAddRateLimitStubs:
    def test_sets_three_placeholder_headers(self) -> None:
        h = _empty_headers()
        _add_rate_limit_stubs(h)
        assert h["x-ratelimit-limit"] == "0"
        assert h["x-ratelimit-remaining"] == "0"
        assert h["x-ratelimit-reset"] == "0"


# ── RequestEnvelopeMiddleware ──


@pytest.mark.asyncio
class TestRequestEnvelopeMiddleware:
    async def test_passes_through_non_http_scopes(self) -> None:
        # lifespan / websocket scopes skip the whole pipeline — the
        # middleware explicitly guards on ``scope["type"] != "http"``.
        sent: list[Message] = []

        async def _lifespan(scope: Scope, receive: Receive, send: Send) -> None:
            await send({"type": "lifespan.startup.complete"})

        async def _send(m: Message) -> None:
            sent.append(m)

        mw = RequestEnvelopeMiddleware(_lifespan)
        await mw(cast(Scope, {"type": "lifespan"}), _noop_receive, _send)
        assert sent == [{"type": "lifespan.startup.complete"}]

    async def test_injects_X_Request_ID_on_http_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.middlewares.envelope.generate_correlation_id",
            lambda: "test-cid-123",
        )
        monkeypatch.setattr(
            "rapidly.middlewares.envelope.geolocate",
            lambda ip: None,
        )
        captured, send = _capture()
        mw = RequestEnvelopeMiddleware(_downstream())
        await mw(
            cast(
                Scope,
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/x",
                    "client": ("1.2.3.4", 0),
                },
            ),
            _noop_receive,
            send,
        )
        headers = {
            k.decode(): v.decode()
            for k, v in cast(list[tuple[bytes, bytes]], captured[0]["headers"])
        }
        assert headers["x-request-id"] == "test-cid-123"

    async def test_injects_all_security_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.middlewares.envelope.generate_correlation_id",
            lambda: "cid",
        )
        monkeypatch.setattr(
            "rapidly.middlewares.envelope.geolocate",
            lambda ip: None,
        )
        captured, send = _capture()
        mw = RequestEnvelopeMiddleware(_downstream())
        await mw(
            cast(
                Scope,
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/x",
                    "client": None,
                },
            ),
            _noop_receive,
            send,
        )
        headers = {
            k.decode(): v.decode()
            for k, v in cast(list[tuple[bytes, bytes]], captured[0]["headers"])
        }
        # Each security header is present — the presence matrix is
        # the actual invariant; the exact values are pinned separately
        # by ``TestAddSecurityHeaders``.
        for h in (
            "x-content-type-options",
            "x-frame-options",
            "strict-transport-security",
            "cache-control",
            "content-security-policy",
            "referrer-policy",
            "permissions-policy",
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
        ):
            assert h in headers, f"missing header: {h}"

    async def test_geolocates_client_ip_and_binds_to_scope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Stub geolocate so we can assert the middleware called it with
        # the right IP AND wrote the result onto the scope for
        # downstream consumers.
        monkeypatch.setattr(
            "rapidly.middlewares.envelope.generate_correlation_id", lambda: "c"
        )
        monkeypatch.setattr(
            "rapidly.middlewares.envelope.geolocate",
            lambda ip: {"country": "US", "ip": ip},
        )

        seen_scopes: list[Scope] = []

        async def _app(scope: Scope, receive: Receive, send: Send) -> None:
            seen_scopes.append(scope)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        _, send = _capture()
        mw = RequestEnvelopeMiddleware(_app)
        await mw(
            cast(
                Scope,
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/",
                    "client": ("8.8.8.8", 0),
                },
            ),
            _noop_receive,
            send,
        )
        # Scope["geo"] populated from the geolocate result.
        assert seen_scopes[0]["geo"] == {"country": "US", "ip": "8.8.8.8"}

    async def test_geo_is_None_when_client_is_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.middlewares.envelope.generate_correlation_id", lambda: "c"
        )
        monkeypatch.setattr("rapidly.middlewares.envelope.geolocate", lambda ip: None)
        seen: list[Scope] = []

        async def _app(scope: Scope, receive: Receive, send: Send) -> None:
            seen.append(scope)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        _, send = _capture()
        mw = RequestEnvelopeMiddleware(_app)
        await mw(
            cast(
                Scope,
                {"type": "http", "method": "GET", "path": "/", "client": None},
            ),
            _noop_receive,
            send,
        )
        assert seen[0]["geo"] is None

    async def test_unbinds_structlog_context_after_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The middleware binds correlation_id / method / path and MUST
        # unbind them in a ``finally`` so context doesn't leak across
        # concurrent requests on the same event loop.
        monkeypatch.setattr(
            "rapidly.middlewares.envelope.generate_correlation_id", lambda: "c"
        )
        monkeypatch.setattr("rapidly.middlewares.envelope.geolocate", lambda ip: None)
        _, send = _capture()
        mw = RequestEnvelopeMiddleware(_downstream())
        await mw(
            cast(
                Scope,
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/ctx",
                    "client": None,
                },
            ),
            _noop_receive,
            send,
        )
        # After the call, the context vars the middleware bound are gone.
        context: dict[str, Any] = structlog.contextvars.get_contextvars()
        for key in ("correlation_id", "method", "path"):
            assert key not in context, f"context leaked: {key} in {context}"

    async def test_unbinds_context_even_if_downstream_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "rapidly.middlewares.envelope.generate_correlation_id", lambda: "c"
        )
        monkeypatch.setattr("rapidly.middlewares.envelope.geolocate", lambda ip: None)

        async def _exploding(scope: Scope, receive: Receive, send: Send) -> None:
            raise RuntimeError("boom")

        _, send = _capture()
        mw = RequestEnvelopeMiddleware(_exploding)
        with pytest.raises(RuntimeError):
            await mw(
                cast(
                    Scope,
                    {
                        "type": "http",
                        "method": "GET",
                        "path": "/x",
                        "client": None,
                    },
                ),
                _noop_receive,
                send,
            )
        # Context must still be cleared — the ``finally`` branch runs.
        context = structlog.contextvars.get_contextvars()
        for key in ("correlation_id", "method", "path"):
            assert key not in context
