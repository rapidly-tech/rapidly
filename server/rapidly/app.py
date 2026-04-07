"""Rapidly application factory and ASGI lifespan management.

Creates the FastAPI application with the full middleware stack, exception
handlers, CORS policy, and router tree.  Module-level side effects
(Sentry, Logfire, PostHog) are executed at import time so that they
instrument the process before any request arrives.
"""

import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypedDict

import structlog
from fastapi import FastAPI
from fastapi.routing import APIRoute

from rapidly import worker  # noqa
from rapidly.admin import app as admin_app
from rapidly.api import router
from rapidly.config import settings
from rapidly.core.cors import CORSConfig, CORSMatcherMiddleware, Scope
from rapidly.core.db.postgres import (
    AsyncEngine,
    AsyncSessionMaker,
    Engine,
    SyncSessionMaker,
    create_async_sessionmaker,
    create_sync_sessionmaker,
)
from rapidly.exception_handlers import add_exception_handlers
from rapidly.health.api import router as health_router
from rapidly.identity.auth.middlewares import AuthPrincipalMiddleware
from rapidly.identity.oauth2.api.well_known import router as well_known_router
from rapidly.identity.oauth2.exception_handlers import (
    OAuth2Error,
    oauth2_error_exception_handler,
)
from rapidly.logfire import (
    configure_logfire,
    instrument_fastapi,
    instrument_httpx,
    instrument_sqlalchemy,
)
from rapidly.logging import Logger
from rapidly.logging import configure as configure_logging
from rapidly.messaging.webhook.webhooks import document_webhooks
from rapidly.middlewares import (
    JobDispatchMiddleware,
    RequestEnvelopeMiddleware,
    RouteNormalizationMiddleware,
    SandboxHeaderMiddleware,
)
from rapidly.observability.http_middleware import RequestMetricsMiddleware
from rapidly.observability.remote_write import (
    start_remote_write_pusher,
    stop_remote_write_pusher,
)
from rapidly.observability.slo import start_slo_metrics, stop_slo_metrics
from rapidly.openapi import OPENAPI_PARAMETERS, set_openapi_generator
from rapidly.platform.search.api import router as search_router
from rapidly.postgres import (
    AsyncSessionMiddleware,
    create_async_engine,
    create_async_read_engine,
    create_sync_engine,
)
from rapidly.posthog import configure_posthog
from rapidly.redis import Redis, create_redis
from rapidly.sentry import configure_sentry

from . import rate_limit

__all__ = ["create_app", "on_shutdown", "on_startup"]

_log: Logger = structlog.get_logger(__name__)

# Legacy API prefix that gets rewritten to /api.
_LEGACY_API_PREFIX: str = r"^/v1"
_CURRENT_API_PREFIX: str = "/api"


# ── Lifecycle hook registry ───────────────────────────────────────

_startup_hooks: list[Callable[[], Awaitable[None]]] = []
_shutdown_hooks: list[Callable[[], Awaitable[None]]] = []


def on_startup(fn: Callable[[], Awaitable[None]]) -> Callable[[], Awaitable[None]]:
    """Register a coroutine to run during application startup."""
    _startup_hooks.append(fn)
    return fn


def on_shutdown(fn: Callable[[], Awaitable[None]]) -> Callable[[], Awaitable[None]]:
    """Register a coroutine to run during application shutdown."""
    _shutdown_hooks.append(fn)
    return fn


# ── CORS ───────────────────────────────────────────────────────────────


def _configure_cors(app: FastAPI) -> None:
    # Config-driven CORS policy
    """Apply a two-tier CORS policy: credentialed for the dashboard, open for API."""
    configs: list[CORSConfig] = []

    # Build the credentialed origin list from settings.CORS_ORIGINS.
    allowed_origins: list[str] = (
        [str(o) for o in settings.CORS_ORIGINS] if settings.CORS_ORIGINS else []
    )

    if allowed_origins:
        allowed_origin_set = set(allowed_origins)

        def _dashboard_matcher(origin: str, scope: Scope) -> bool:
            return origin in allowed_origin_set

        configs.append(
            CORSConfig(
                _dashboard_matcher,
                allow_origins=allowed_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        )

    # Public API — no cookies, only Authorization header.
    configs.append(
        CORSConfig(
            lambda origin, scope: True,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization"],
        )
    )

    app.add_middleware(CORSMatcherMiddleware, configs=configs)


# ── OpenAPI helpers ────────────────────────────────────────────────────


def _generate_operation_id(route: APIRoute) -> str:
    """Generate operation IDs in module:action format for API client generation."""
    tag = str(route.tags[0]) if route.tags else "default"
    name = route.name or "unknown"
    return f"{tag}:{name}"


# ── Application state ─────────────────────────────────────────────────


class State(TypedDict):
    """Typed lifespan state shared via ``request.state``."""

    async_engine: AsyncEngine
    async_sessionmaker: AsyncSessionMaker
    async_read_engine: AsyncEngine
    async_read_sessionmaker: AsyncSessionMaker
    sync_engine: Engine
    sync_sessionmaker: SyncSessionMaker
    redis: Redis


# ── Lifespan ───────────────────────────────────────────────────────────


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    """Manage database engines, Redis, and observability background threads."""
    _log.info("app.starting")

    metrics_enabled = start_remote_write_pusher(include_queue_metrics=False)
    if metrics_enabled:
        _log.info("app.metrics.enabled")

    start_slo_metrics()

    # Primary async engine (may also serve reads if no replica configured).
    async_engine = async_read_engine = create_async_engine("app")
    async_sessionmaker = async_read_sessionmaker = create_async_sessionmaker(
        async_engine
    )
    instrument_engines = [async_engine.sync_engine]

    if settings.is_read_replica_configured():
        async_read_engine = create_async_read_engine("app")
        async_read_sessionmaker = create_async_sessionmaker(async_read_engine)
        instrument_engines.append(async_read_engine.sync_engine)

    sync_engine = create_sync_engine("app")
    sync_sessionmaker = create_sync_sessionmaker(sync_engine)
    instrument_engines.append(sync_engine)
    instrument_sqlalchemy(instrument_engines)

    redis = create_redis("app")

    # Run registered startup hooks
    for hook in _startup_hooks:
        await hook()

    _log.info("app.started")

    yield {
        "async_engine": async_engine,
        "async_sessionmaker": async_sessionmaker,
        "async_read_engine": async_read_engine,
        "async_read_sessionmaker": async_read_sessionmaker,
        "sync_engine": sync_engine,
        "sync_sessionmaker": sync_sessionmaker,
        "redis": redis,
    }

    # Run registered shutdown hooks
    for hook in _shutdown_hooks:
        await hook()

    # ── Teardown ───────────────────────────────────────────────────────
    stop_slo_metrics()
    stop_remote_write_pusher()

    await redis.close(True)
    await async_engine.dispose()
    if async_read_engine is not async_engine:
        await async_read_engine.dispose()
    sync_engine.dispose()

    _log.info("app.stopped")


# ── Factory ────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Assemble the FastAPI app with the full middleware stack and router tree."""
    app = FastAPI(
        generate_unique_id_function=_generate_operation_id,
        lifespan=lifespan,
        **OPENAPI_PARAMETERS,
    )

    # ── Middleware (outermost → innermost) ─────────────────────────────
    if settings.is_sandbox():
        app.add_middleware(SandboxHeaderMiddleware)
    if not settings.is_testing():
        app.add_middleware(rate_limit.get_middleware)
        app.add_middleware(AuthPrincipalMiddleware)
        app.add_middleware(JobDispatchMiddleware)
        app.add_middleware(AsyncSessionMiddleware)
    app.add_middleware(
        RouteNormalizationMiddleware,
        pattern=_LEGACY_API_PREFIX,
        replacement=_CURRENT_API_PREFIX,
    )
    if not settings.is_testing():
        app.add_middleware(RequestMetricsMiddleware)

    _configure_cors(app)
    app.add_middleware(RequestEnvelopeMiddleware, enable_hsts=not settings.is_testing())

    # ── Exception handlers ─────────────────────────────────────────────
    add_exception_handlers(app)
    app.add_exception_handler(OAuth2Error, oauth2_error_exception_handler)  # pyright: ignore

    # ── Routers ────────────────────────────────────────────────────────
    app.include_router(well_known_router)  # OIDC discovery endpoints
    app.include_router(health_router)  # liveness probe
    app.include_router(search_router)  # full-text search

    if settings.ADMIN_HOST is None:
        app.mount("/admin", admin_app)
    else:
        app.host(settings.ADMIN_HOST, admin_app)

    app.include_router(router)
    document_webhooks(app)

    return app


# ── Module-level instrumentation (runs once at import) ─────────────────
configure_sentry()
configure_logfire("server")
configure_logging(logfire=True)
configure_posthog()

app = create_app()
set_openapi_generator(app)
instrument_fastapi(app)
instrument_httpx()
