"""Worker health-check server and heartbeat monitoring.

Runs a lightweight HTTP health-check endpoint inside the Dramatiq
worker process and monitors actor heartbeats so that stale workers
can be detected by orchestration tooling (Docker, Kubernetes).
"""

import asyncio
import contextlib
import os
from collections.abc import AsyncGenerator, Callable, Mapping
from datetime import timedelta
from typing import Any

import structlog
import uvicorn
from dramatiq.middleware import Middleware
from redis import RedisError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from rapidly.analytics.external_event.queries import ExternalEventRepository
from rapidly.config import settings
from rapidly.core.db.postgres import AsyncSessionMaker, create_async_sessionmaker
from rapidly.core.utils import now_utc
from rapidly.logging import Logger
from rapidly.messaging.webhook.queries import WebhookEventRepository
from rapidly.postgres import create_async_engine, create_async_read_engine
from rapidly.redis import Redis, create_redis

_log: Logger = structlog.get_logger()

HTTP_HOST = os.getenv("dramatiq_prom_host", "0.0.0.0")
HTTP_PORT = int(os.getenv("dramatiq_prom_port", "9191"))


# ── Health Checks ──


class HealthMiddleware(Middleware):
    @property
    def forks(self) -> list[Callable[[], int]]:
        return [_run_exposition_server]


async def health(request: Request) -> JSONResponse:
    try:
        redis: Redis = request.state.redis
        await redis.ping()
    except RedisError as e:
        raise HTTPException(status_code=503, detail="Redis is not available") from e

    return JSONResponse({"status": "ok"})


# ── Reporting ──

UNDELIVERED_WEBHOOKS_MINIMUM_AGE = timedelta(minutes=5)
UNDELIVERED_WEBHOOKS_ALERT_THRESHOLD = 10

UNHANDLED_EXTERNAL_EVENTS_MINIMUM_AGE = timedelta(minutes=5)
UNHANDLED_EXTERNAL_EVENTS_ALERT_THRESHOLD = 10


async def webhooks(request: Request) -> JSONResponse:
    async_sessionmaker: AsyncSessionMaker = request.state.async_sessionmaker
    async with async_sessionmaker() as session:
        repository = WebhookEventRepository(session)
        undelivered_webhooks = await repository.get_all_undelivered(
            older_than=now_utc() - UNDELIVERED_WEBHOOKS_MINIMUM_AGE
        )
        if len(undelivered_webhooks) > UNDELIVERED_WEBHOOKS_ALERT_THRESHOLD:
            return JSONResponse(
                {
                    "status": "error",
                    "undelivered_webhooks": len(undelivered_webhooks),
                },
                status_code=503,
            )

    return JSONResponse({"status": "ok"})


async def external_events(request: Request) -> JSONResponse:
    async_sessionmaker: AsyncSessionMaker = request.state.async_sessionmaker
    async with async_sessionmaker() as session:
        repository = ExternalEventRepository(session)
        unhandled_events = await repository.get_all_unhandled(
            older_than=now_utc() - UNHANDLED_EXTERNAL_EVENTS_MINIMUM_AGE
        )
        if len(unhandled_events) > UNHANDLED_EXTERNAL_EVENTS_ALERT_THRESHOLD:
            return JSONResponse(
                {
                    "status": "error",
                    "unhandled_external_events": len(unhandled_events),
                },
                status_code=503,
            )

    return JSONResponse({"status": "ok"})


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[Mapping[str, Any]]:
    if settings.is_read_replica_configured():
        async_engine = create_async_read_engine("worker")
    else:
        async_engine = create_async_engine("worker")
    async_sessionmaker = create_async_sessionmaker(async_engine)
    redis = create_redis("worker")

    yield {
        "redis": redis,
        "async_sessionmaker": async_sessionmaker,
    }

    await redis.close()
    await async_engine.dispose()


def create_app() -> Starlette:
    routes = [
        Route("/", health, methods=["GET"]),
        Route("/webhooks", webhooks, methods=["GET"]),
        Route("/unhandled-external-events", external_events, methods=["GET"]),
    ]
    return Starlette(routes=routes, lifespan=lifespan)


def _run_exposition_server() -> int:
    _log.debug("Starting exposition server...")
    app = create_app()
    config = uvicorn.Config(
        app, host=HTTP_HOST, port=HTTP_PORT, log_level="error", access_log=False
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    except asyncio.CancelledError:
        pass

    return 0
