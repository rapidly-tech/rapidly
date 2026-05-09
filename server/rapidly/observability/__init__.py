"""Prometheus metric definitions for HTTP, task, and file-sharing subsystems."""

from rapidly.observability.file_sharing_metrics import (
    FILE_SHARING_PG_WRITE_DURATION_SECONDS,
    FILE_SHARING_PG_WRITE_TOTAL,
    FILE_SHARING_SESSION_TOTAL,
)
from rapidly.observability.http_metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUEST_TOTAL,
    METRICS_DENY_LIST,
)
from rapidly.observability.metrics import (
    GC_COLLECTION_DURATION,
    TASK_DEBOUNCE_DELAY,
    TASK_DEBOUNCED,
    TASK_DURATION,
    TASK_EXECUTIONS,
    TASK_RETRIES,
    register_gc_metrics,
)

__all__ = [
    # File sharing metrics (dual-write)
    "FILE_SHARING_PG_WRITE_DURATION_SECONDS",
    "FILE_SHARING_PG_WRITE_TOTAL",
    "FILE_SHARING_SESSION_TOTAL",
    # GC metrics (worker)
    "GC_COLLECTION_DURATION",
    # HTTP metrics (API server)
    "HTTP_REQUEST_DURATION_SECONDS",
    "HTTP_REQUEST_TOTAL",
    "METRICS_DENY_LIST",
    # Task metrics (worker)
    "TASK_DEBOUNCED",
    "TASK_DEBOUNCE_DELAY",
    "TASK_DURATION",
    "TASK_EXECUTIONS",
    "TASK_RETRIES",
    "register_gc_metrics",
]
