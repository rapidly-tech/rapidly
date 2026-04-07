"""HTTP request metrics for SLI/SLO monitoring.

Two Prometheus instruments are exposed:

* ``rapidly_http_request_total`` -- counter of completed requests
  (labels: endpoint, method, status_code)
* ``rapidly_http_request_duration_seconds`` -- histogram of latency
  (labels: endpoint, method)

Endpoints listed in ``METRICS_DENY_LIST`` and ASGI apps registered via
``exclude_app_from_metrics()`` are silently excluded.
"""

import os
from typing import TYPE_CHECKING

from rapidly.config import settings

if TYPE_CHECKING:
    from starlette.types import ASGIApp

# Ensure the multiprocess directory exists before prometheus_client is
# imported so that child workers share a single metric store.
_prom_dir = settings.WORKER_PROMETHEUS_DIR
_prom_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(_prom_dir))

from prometheus_client import Counter, Histogram  # noqa: E402

# ---------------------------------------------------------------------------
# Exclusion sets
# ---------------------------------------------------------------------------

METRICS_DENY_LIST: set[str] = {
    "/healthz",
    "/readyz",
    "/.well-known/openid-configuration",
    "/.well-known/jwks.json",
}

METRICS_EXCLUDED_APPS: set["ASGIApp"] = set()


def exclude_app_from_metrics(app: "ASGIApp") -> None:
    """Register an ASGI sub-application to be excluded from HTTP metrics."""
    METRICS_EXCLUDED_APPS.add(app)


# ---------------------------------------------------------------------------
# Prometheus instruments
# ---------------------------------------------------------------------------

_REQUEST_LABELS = ["endpoint", "method", "status_code"]
_DURATION_LABELS = ["endpoint", "method"]

# Histogram buckets cover sub-millisecond health checks through 30 s SSR pages.
_DURATION_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)

HTTP_REQUEST_TOTAL = Counter(
    "rapidly_http_request_total",
    "Total number of HTTP requests",
    _REQUEST_LABELS,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "rapidly_http_request_duration_seconds",
    "HTTP request duration in seconds",
    _DURATION_LABELS,
    buckets=_DURATION_BUCKETS,
)
