"""Tests for ``rapidly/worker/_health.py``.

Worker health-check server. Container orchestrators (Docker /
Kubernetes) probe these endpoints to decide whether to recycle a
stale worker. Three load-bearing pins:

- ``health`` returns 200 OK on a successful Redis ping; 503 on
  ``RedisError``. Without this, the orchestrator can't distinguish
  a healthy worker from one with a broken Redis connection — and
  would either keep stale workers alive or recycle healthy ones
- Alert thresholds (``UNDELIVERED_WEBHOOKS_ALERT_THRESHOLD = 10``,
  ``UNHANDLED_EXTERNAL_EVENTS_ALERT_THRESHOLD = 10``) — these
  decide when /webhooks and /unhandled-external-events return 503.
  Drift would alter the SRE alarm threshold silently
- ``create_app`` mounts exactly 3 routes (/, /webhooks,
  /unhandled-external-events) — adding routes silently means the
  health-probe orchestration config could go out of sync
"""

from __future__ import annotations

import os
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis import RedisError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.routing import Route

from rapidly.worker._health import (
    HTTP_HOST,
    HTTP_PORT,
    UNDELIVERED_WEBHOOKS_ALERT_THRESHOLD,
    UNDELIVERED_WEBHOOKS_MINIMUM_AGE,
    UNHANDLED_EXTERNAL_EVENTS_ALERT_THRESHOLD,
    UNHANDLED_EXTERNAL_EVENTS_MINIMUM_AGE,
    HealthMiddleware,
    create_app,
    health,
)


class TestConstants:
    def test_alert_thresholds_pinned(self) -> None:
        # Drifting either threshold silently changes the SRE
        # alarm / recycle behaviour. Pinning forces an intentional
        # update.
        assert UNDELIVERED_WEBHOOKS_ALERT_THRESHOLD == 10
        assert UNHANDLED_EXTERNAL_EVENTS_ALERT_THRESHOLD == 10

    def test_minimum_ages_pinned(self) -> None:
        # Don't alarm on transient queue lag — a 5-minute floor
        # excludes normal end-of-batch dwell time from the
        # health-degraded signal.
        assert UNDELIVERED_WEBHOOKS_MINIMUM_AGE == timedelta(minutes=5)
        assert UNHANDLED_EXTERNAL_EVENTS_MINIMUM_AGE == timedelta(minutes=5)

    def test_default_host_and_port(self) -> None:
        # Default exposition port is 9191 — matches the orchestrator
        # probe config baked into the deployment manifest.
        # ``dramatiq_prom_host`` / ``dramatiq_prom_port`` env vars
        # override but the defaults must be stable.
        if "dramatiq_prom_host" not in os.environ:
            assert HTTP_HOST == "0.0.0.0"
        if "dramatiq_prom_port" not in os.environ:
            assert HTTP_PORT == 9191


class TestHealthMiddleware:
    def test_forks_runs_the_exposition_server(self) -> None:
        # The middleware advertises a fork that runs the health
        # HTTP server alongside the worker — pinning the count + name
        # ensures Dramatiq's fork orchestration picks it up.
        from rapidly.worker._health import _run_exposition_server

        mw = HealthMiddleware()
        assert mw.forks == [_run_exposition_server]


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_returns_200_on_successful_redis_ping(self) -> None:
        # Happy path: Redis answered, return 200 with status=ok.
        req = MagicMock()
        req.state.redis.ping = AsyncMock(return_value=True)
        response = await health(req)
        assert response.status_code == 200
        assert response.body == b'{"status":"ok"}'

    async def test_raises_503_when_redis_unavailable(self) -> None:
        # Load-bearing pin. RedisError → 503 means the orchestrator
        # recycles this worker. A regression that swallowed the
        # error would leave broken workers alive in the pool.
        req = MagicMock()
        req.state.redis.ping = AsyncMock(side_effect=RedisError("connection lost"))
        with pytest.raises(HTTPException) as exc_info:
            await health(req)
        assert exc_info.value.status_code == 503
        assert "Redis is not available" in exc_info.value.detail


class TestCreateApp:
    def test_returns_starlette_app(self) -> None:
        app = create_app()
        assert isinstance(app, Starlette)

    def test_mounts_exactly_three_routes(self) -> None:
        # Pin the route set so an accidental addition doesn't go
        # unnoticed by the orchestrator's probe-path config.
        app = create_app()
        route_paths = sorted(r.path for r in app.routes if isinstance(r, Route))
        assert route_paths == sorted(["/", "/webhooks", "/unhandled-external-events"])

    def test_routes_use_get_method(self) -> None:
        # Health probes are GETs by convention; pinning prevents
        # a regression that flipped one to POST and broke the
        # probe.
        app = create_app()
        for route in app.routes:
            if isinstance(route, Route):
                assert "GET" in (route.methods or set())
