"""Service-Level Objective gauge publisher.

Exposes per-endpoint P99-latency and availability targets as Prometheus
gauges so that PromQL alert rules and Grafana dashboards can dynamically
compare *measured* performance against *declared* objectives via
``group_left`` joins.

Lifecycle
---------
Call :func:`start_slo_metrics` during application startup and
:func:`stop_slo_metrics` during shutdown.  A background thread
re-publishes the gauge values every ``_PUBLISH_INTERVAL_SEC`` seconds
to survive Prometheus restarts / metric resets.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import structlog
from prometheus_client import Gauge

_logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Gauge declarations
# ---------------------------------------------------------------------------

SLO_P99_TARGET = Gauge(
    "rapidly_slo_p99_target_seconds",
    "Desired P99 latency ceiling (seconds) per critical endpoint.",
    ["endpoint", "method"],
)

SLO_AVAILABILITY_TARGET = Gauge(
    "rapidly_slo_availability_target",
    "Desired availability floor (percentage) per critical endpoint.",
    ["endpoint", "method"],
)


# ---------------------------------------------------------------------------
# Endpoint objective definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _EndpointSLO:
    """Compact container for a single endpoint's performance contract."""

    path: str
    method: str
    p99_seconds: float
    availability_pct: float


# Paths must match the FastAPI route template exactly — e.g.
# ``/api/file-shares/channels/{slug}`` rather than ``/api/file-shares/channels/abc123``.
_OBJECTIVES: tuple[_EndpointSLO, ...] = (
    _EndpointSLO("/api/file-shares/channels", "POST", 2.5, 99.95),
    _EndpointSLO("/api/file-shares/channels/{slug}", "GET", 1.2, 99.95),
    _EndpointSLO("/api/file-shares/channels/{slug}/checkout", "POST", 5.5, 99.95),
    _EndpointSLO("/api/file-shares/sessions", "GET", 1.2, 99.95),
    _EndpointSLO(
        "/api/file-shares/channels/{slug}/download-complete", "POST", 2.5, 99.95
    ),
    _EndpointSLO("/api/file-shares/channels/{slug}/reader-token", "POST", 1.2, 99.95),
)

# ---------------------------------------------------------------------------
# Background refresh machinery
# ---------------------------------------------------------------------------

_PUBLISH_INTERVAL_SEC: int = 300  # 5 minutes

_stop_flag: threading.Event | None = None
_worker_thread: threading.Thread | None = None


def _publish_gauges() -> None:
    """Push every objective's values into the Prometheus gauges."""
    for obj in _OBJECTIVES:
        labels = {"endpoint": obj.path, "method": obj.method}
        SLO_P99_TARGET.labels(**labels).set(obj.p99_seconds)
        SLO_AVAILABILITY_TARGET.labels(**labels).set(obj.availability_pct)


def _background_loop(stop: threading.Event) -> None:
    """Periodically re-publish gauges until signalled to stop."""
    while not stop.wait(timeout=_PUBLISH_INTERVAL_SEC):
        try:
            _publish_gauges()
        except Exception:
            _logger.exception("slo_gauge_refresh_failed")


# ---------------------------------------------------------------------------
# Public lifecycle API
# ---------------------------------------------------------------------------


def start_slo_metrics() -> None:
    """Publish SLO gauges immediately and launch periodic refresh."""
    global _stop_flag, _worker_thread

    _publish_gauges()

    if _worker_thread is not None:
        return  # already running

    _stop_flag = threading.Event()
    _worker_thread = threading.Thread(
        target=_background_loop,
        args=(_stop_flag,),
        daemon=True,
        name="slo-gauge-publisher",
    )
    _worker_thread.start()
    _logger.info("slo_metrics.started", interval_sec=_PUBLISH_INTERVAL_SEC)


def stop_slo_metrics() -> None:
    """Shut down the periodic refresh thread, blocking up to 5 s."""
    global _stop_flag, _worker_thread

    if _stop_flag is not None:
        _stop_flag.set()

    if _worker_thread is not None:
        _worker_thread.join(timeout=5.0)
        _worker_thread = None
        _stop_flag = None

    _logger.info("slo_metrics.stopped")
