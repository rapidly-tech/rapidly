"""Tests for ``rapidly/core/cors.py``.

Two-tier CORS routing. Five load-bearing surfaces:

- ``_PREFLIGHT_MAX_AGE`` is pinned to ``600`` (10 minutes) — the
  documented browser preflight cache window. Drift to a longer
  window would let stale CORS rules linger across deploys; drift
  shorter would burn CPU on preflights for every request.
- ``CORSConfig`` defaults: ``allow_methods=("GET",)``,
  ``allow_credentials=False``. These are the safe defaults — drift
  to allow-everything would expose write endpoints to cross-origin
  requests; drift to default-credentials-true would let third-party
  origins ride the user's cookie.
- The ``CORSMatcherMiddleware`` ROUTES to the FIRST matching
  config (priority order). Drift to the last-match would let a
  permissive public-API rule shadow a credentialed dashboard
  rule. Configs whose matcher returns False are skipped.
- Requests with no ``Origin`` header SKIP CORS handling
  entirely (same-origin / server-to-server requests). Drift to
  apply CORS would emit cross-origin headers on cookies the
  browser already trusts.
- Non-HTTP scopes (websocket, lifespan) bypass CORS. Drift would
  500 on every websocket connection.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from rapidly.core.cors import (
    _PREFLIGHT_MAX_AGE,
    CORSConfig,
    CORSMatcherMiddleware,
)


def _http_scope(
    *,
    method: str = "GET",
    origin: str | None = "https://example.com",
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    headers: list[tuple[bytes, bytes]] = []
    if origin is not None:
        headers.append((b"origin", origin.encode("latin-1")))
    if extra_headers:
        for k, v in extra_headers.items():
            headers.append((k.encode("latin-1"), v.encode("latin-1")))
    return {
        "type": "http",
        "method": method,
        "path": "/x",
        "headers": headers,
    }


def _async_app() -> AsyncMock:
    return AsyncMock()


class TestPreflightMaxAge:
    def test_pinned_to_ten_minutes(self) -> None:
        # Pin: 600s preflight cache. Drift longer would let stale
        # CORS rules linger across deploys; drift shorter would
        # burn CPU on preflight for every request.
        assert _PREFLIGHT_MAX_AGE == 600


class TestCORSConfigDefaults:
    def test_default_methods_only_get(self) -> None:
        # Pin: GET-only. Drift to allow-everything would expose
        # write endpoints to cross-origin requests by default.
        config = CORSConfig(matcher=lambda origin, scope: True)
        assert config.allow_methods == ("GET",)

    def test_default_credentials_false(self) -> None:
        # Pin: credentials disabled by default. Drift to True
        # would let third-party origins ride the user's cookie.
        config = CORSConfig(matcher=lambda origin, scope: True)
        assert config.allow_credentials is False

    def test_default_max_age_uses_preflight_cache(self) -> None:
        # Pin: ``max_age`` defaults to the module constant — drift
        # to a hardcoded value would diverge from the pinned 600s.
        config = CORSConfig(matcher=lambda origin, scope: True)
        assert config.max_age == _PREFLIGHT_MAX_AGE

    def test_dataclass_is_frozen_and_slotted(self) -> None:
        # Pin: configs are immutable + slotted (cheap in middleware
        # init's tuple copy). Drift to add __dict__ would bloat
        # memory; drift to mutable would let runtime mutation
        # silently change CORS routing mid-request.
        config = CORSConfig(matcher=lambda origin, scope: True)
        assert not hasattr(config, "__dict__")
        with pytest.raises(dataclasses_FrozenInstanceError()):
            config.allow_methods = ("POST",)  # type: ignore[misc]


def dataclasses_FrozenInstanceError() -> type[Exception]:
    """Lazy import — keeps the import set tidy."""
    from dataclasses import FrozenInstanceError

    return FrozenInstanceError


@pytest.mark.asyncio
class TestNoOriginBypass:
    async def test_no_origin_header_skips_cors_entirely(self) -> None:
        # Pin: same-origin / server-to-server requests carry no
        # ``Origin`` header — they bypass CORS handling. Drift
        # would add cross-origin headers to cookies the browser
        # already trusts.
        app = _async_app()
        called_matcher: list[bool] = []

        def _record_and_match(origin: str, scope: Any) -> bool:
            called_matcher.append(True)
            return True

        config = CORSConfig(matcher=_record_and_match)
        middleware = CORSMatcherMiddleware(app, configs=[config])

        scope = _http_scope(origin=None)
        await middleware(scope, AsyncMock(), AsyncMock())

        # The matcher MUST NOT have been called (we short-
        # circuited before ever consulting it).
        assert called_matcher == []
        # The downstream app was invoked.
        app.assert_called_once()


@pytest.mark.asyncio
class TestNonHttpScopeBypass:
    async def test_websocket_scope_bypasses_cors(self) -> None:
        # Pin: only ``http`` scopes pass through CORS. Drift to
        # websockets would 500 on every WS connection (Starlette's
        # CORSMiddleware doesn't speak ws).
        app = _async_app()
        config = CORSConfig(matcher=lambda origin, scope: True)
        middleware = CORSMatcherMiddleware(app, configs=[config])

        scope = {"type": "websocket", "path": "/ws", "headers": []}
        await middleware(scope, AsyncMock(), AsyncMock())

        app.assert_called_once()


@pytest.mark.asyncio
class TestFirstMatchWins:
    async def test_first_matching_rule_wins(self) -> None:
        # Pin: rules are evaluated in order; first ``True`` from
        # ``matcher`` wins. Drift to last-wins would let a
        # permissive public rule shadow a credentialed dashboard
        # rule.
        app = _async_app()

        match_log: list[str] = []

        def _make_matcher(name: str, ret: bool) -> Any:
            def _m(origin: str, scope: Any) -> bool:
                match_log.append(name)
                return ret

            return _m

        first = CORSConfig(matcher=_make_matcher("first", True))
        second = CORSConfig(matcher=_make_matcher("second", True))

        middleware = CORSMatcherMiddleware(app, configs=[first, second])

        scope = _http_scope()
        await middleware(scope, AsyncMock(), AsyncMock())

        # Only ``first`` was consulted before short-circuit.
        assert match_log == ["first"]


@pytest.mark.asyncio
class TestNoMatchPassThrough:
    async def test_unmatched_origin_passes_through_without_cors(self) -> None:
        # Pin: an origin not matched by any rule does NOT get CORS
        # headers added. Drift to fail-open would emit
        # ``Access-Control-Allow-Origin: *`` on third-party origins.
        app = _async_app()

        config = CORSConfig(matcher=lambda origin, scope: False)
        middleware = CORSMatcherMiddleware(app, configs=[config])

        scope = _http_scope(origin="https://attacker.example")
        await middleware(scope, AsyncMock(), AsyncMock())

        # Downstream app called WITHOUT routing through Starlette's
        # CORSMiddleware (no CORS headers added at this layer).
        app.assert_called_once()


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: documented public surface is the two main classes
        # plus the Scope re-export (used by callers writing custom
        # matchers).
        from rapidly.core import cors as M

        assert set(M.__all__) == {"CORSConfig", "CORSMatcherMiddleware", "Scope"}
