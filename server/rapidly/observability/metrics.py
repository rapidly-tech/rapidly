"""Prometheus metric definitions for the Rapidly worker subsystem.

Covers background-task throughput, retry behaviour, debounce activity,
and Python garbage-collection pauses.  The ``PROMETHEUS_MULTIPROC_DIR``
environment variable is set as a side-effect of importing this module,
which **must** happen before ``prometheus_client`` is imported elsewhere.
"""

from __future__ import annotations

import gc
import os
import time
from typing import Final

from rapidly.config import settings

# ── Bootstrap multi-process metric sharing ────────────────────────────
# Workers fork a lightweight health-check server, so all processes must
# write to the same shared directory.

_prom_dir = settings.WORKER_PROMETHEUS_DIR
_prom_dir.mkdir(parents=True, exist_ok=True)
os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(_prom_dir)

from prometheus_client import Counter, Histogram  # noqa: E402

# ── Task execution metrics ────────────────────────────────────────────

TASK_EXECUTIONS = Counter(
    "rapidly_task_executions_total",
    "Cumulative task completions partitioned by outcome.",
    ["queue", "task_name", "status"],
)

TASK_DURATION = Histogram(
    "rapidly_task_duration_seconds",
    "Wall-clock time per task execution.",
    ["queue", "task_name"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

TASK_RETRIES = Counter(
    "rapidly_task_retries_total",
    "How often individual tasks have been retried.",
    ["queue", "task_name"],
)

# ── Debounce metrics ─────────────────────────────────────────────────

TASK_DEBOUNCED = Counter(
    "rapidly_task_debounced_total",
    "Tasks suppressed by the debounce middleware.",
    ["queue", "task_name"],
)

TASK_DEBOUNCE_DELAY = Histogram(
    "rapidly_task_debounce_delay_seconds",
    "Elapsed time from first enqueue to actual execution for debounced tasks.",
    ["queue", "task_name"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0),
)

# ── Garbage-collection timing ────────────────────────────────────────

GC_COLLECTION_DURATION = Histogram(
    "rapidly_gc_collection_seconds",
    "Duration of CPython garbage-collection cycles by generation.",
    ["generation"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

_GC_PHASE_STARTED_AT: Final[str] = "__gc_phase_start"

# We store the start timestamp in a dict keyed by a sentinel so that
# concurrent GC callbacks (theoretically impossible but defensive) do
# not collide via a bare global.
_gc_state: dict[str, float] = {}


def _on_gc_phase(phase: str, info: dict[str, int]) -> None:
    gen_label = str(info["generation"])
    if phase == "start":
        _gc_state[_GC_PHASE_STARTED_AT] = time.perf_counter()
    elif phase == "stop":
        started = _gc_state.pop(_GC_PHASE_STARTED_AT, None)
        if started is not None:
            GC_COLLECTION_DURATION.labels(generation=gen_label).observe(
                time.perf_counter() - started
            )


def register_gc_metrics() -> None:
    """Install the GC callback if it is not already registered."""
    if _on_gc_phase not in gc.callbacks:
        gc.callbacks.append(_on_gc_phase)
