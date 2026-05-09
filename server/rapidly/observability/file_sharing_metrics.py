"""
File sharing dual-write metrics.

Tracks PG dual-write operations alongside Redis to monitor
data consistency, write latency, and failure rates.

Metrics:
- rapidly_file_sharing_pg_write_total: Counter of PG write operations by type and status
- rapidly_file_sharing_pg_write_duration_seconds: Histogram of PG write latency
- rapidly_file_sharing_session_total: Counter of sessions by status transition
"""

import os

from rapidly.config import settings

# Setup multiprocess prometheus directory before importing prometheus_client
prometheus_dir = settings.WORKER_PROMETHEUS_DIR
prometheus_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(prometheus_dir))

from prometheus_client import Counter, Histogram  # noqa: E402

FILE_SHARING_PG_WRITE_TOTAL = Counter(
    "rapidly_file_sharing_pg_write_total",
    "Total PG dual-write operations",
    ["operation", "status"],
)

FILE_SHARING_PG_WRITE_DURATION_SECONDS = Histogram(
    "rapidly_file_sharing_pg_write_duration_seconds",
    "PG dual-write operation latency in seconds",
    ["operation"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

FILE_SHARING_SESSION_TOTAL = Counter(
    "rapidly_file_sharing_session_total",
    "Total file sharing sessions by status transition",
    ["status"],
)
