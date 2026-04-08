"""Logfire distributed-tracing setup for Rapidly.

Configures the Logfire SDK with custom sampling (health-check suppression,
log-level filtering) and provides thin wrappers that instrument FastAPI,
HTTPX, and SQLAlchemy.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, Literal, cast

import httpx
import logfire
from fastapi import FastAPI
from logfire.sampling import SpanLevel
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    SamplingResult,
)

if TYPE_CHECKING:
    from opentelemetry.context import Context
    from opentelemetry.trace import Link, SpanKind
    from opentelemetry.trace.span import TraceState
    from opentelemetry.util.types import Attributes

from rapidly.config import settings
from rapidly.core.db.postgres import Engine
from rapidly.observability.otel_prometheus import PrometheusMeterProvider

# A predicate that decides whether a span should be dropped.
SpanMatcher = Callable[[str, "Attributes | None"], bool]


# -- Sampling ----------------------------------------------------------------


def _is_health_probe(name: str, attrs: Attributes | None) -> bool:
    """Match the ``/healthz`` endpoint used by load balancers."""
    return attrs is not None and attrs.get("http.route") == "/healthz"


def _is_worker_heartbeat(name: str, attrs: Attributes | None) -> bool:
    """Match noisy worker health-check spans."""
    lowered = name.lower()
    return lowered.startswith("recording health:") or lowered.startswith(
        "health check successful"
    )


# Registered matchers — add new ones here to drop additional noisy spans.
_DROP_MATCHERS: tuple[SpanMatcher, ...] = (_is_health_probe, _is_worker_heartbeat)


class DropMatchedSampler(Sampler):
    """Sampler that drops spans matching any of the provided predicates."""

    def __init__(self, matchers: Sequence[SpanMatcher]) -> None:
        super().__init__()
        self._matchers = matchers

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes | None = None,
        links: Sequence[Link] | None = None,
        trace_state: TraceState | None = None,
    ) -> SamplingResult:
        decision = ALWAYS_ON
        if any(m(name, attributes) for m in self._matchers):
            decision = ALWAYS_OFF

        return decision.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state
        )

    def get_description(self) -> str:
        return "DropMatchedSampler"


class MinimumLevelSampler(Sampler):
    """Sampler that drops log-level spans below the configured threshold."""

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes | None = None,
        links: Sequence[Link] | None = None,
        trace_state: TraceState | None = None,
    ) -> SamplingResult:
        decision = ALWAYS_ON

        if attributes:
            level_num = attributes.get("logfire.level_num")
            if level_num is not None:
                threshold = cast(logfire.LevelName, settings.LOG_LEVEL.lower())
                if SpanLevel(cast(int, level_num)) < threshold:
                    decision = ALWAYS_OFF

        return decision.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state
        )

    def get_description(self) -> str:
        return "MinimumLevelSampler"


# -- Scrubbing ---------------------------------------------------------------


def _scrub_callback(match: logfire.ScrubMatch) -> Any | None:
    # Preserve the auth subject attribute — it is not PII.
    if match.path == ("attributes", "subject"):
        return match.value
    return None


# -- Public API ---------------------------------------------------------------


def configure_logfire(service_name: Literal["server", "worker"]) -> None:
    """Initialise Logfire with Rapidly's sampling and scrubbing policy."""
    resolved_name = os.environ.get("RENDER_SERVICE_NAME", service_name)
    level_threshold = cast(logfire.LevelName, settings.LOG_LEVEL.lower())

    logfire.configure(
        send_to_logfire="if-token-present",
        token=settings.LOGFIRE_TOKEN,
        service_name=resolved_name,
        service_version=os.environ.get("RELEASE_VERSION", "development"),
        console=False,
        sampling=logfire.SamplingOptions.level_or_duration(
            head=ParentBased(
                DropMatchedSampler(_DROP_MATCHERS),
                local_parent_sampled=MinimumLevelSampler(),
            ),
            level_threshold=level_threshold,
        ),
        scrubbing=logfire.ScrubbingOptions(callback=_scrub_callback),
    )


def instrument_httpx(client: httpx.AsyncClient | httpx.Client | None = None) -> None:
    """Instrument a specific HTTPX client, or all clients globally."""
    instrumentor = HTTPXClientInstrumentor()
    if client is not None:
        instrumentor.instrument_client(client)
    else:
        instrumentor.instrument()


def instrument_fastapi(app: FastAPI) -> None:
    """Attach Logfire tracing to a FastAPI application."""
    logfire.instrument_fastapi(app, capture_headers=True)


_prometheus_meter = PrometheusMeterProvider()


def instrument_sqlalchemy(engines: Sequence[Engine]) -> None:
    """Instrument SQLAlchemy engines with Logfire + Prometheus metrics."""
    logfire.instrument_sqlalchemy(engines=engines, meter_provider=_prometheus_meter)


__all__ = [
    "configure_logfire",
    "instrument_fastapi",
    "instrument_httpx",
    "instrument_sqlalchemy",
]
