"""Prometheus Remote Write v1 client.

Periodically serialises all multi-process Prometheus metrics into the
Remote Write wire format (protobuf + Snappy compression) and POSTs them
to a configurable endpoint (Grafana Cloud, Thanos, Mimir, etc.).

The protobuf encoding is hand-rolled because there is no maintained
first-party Python library for Remote Write.

Protocol reference: https://prometheus.io/docs/specs/prw/remote_write_spec/
"""

from __future__ import annotations

import asyncio
import base64
import fcntl
import math
import os
import socket
import struct
import threading
import time
from collections.abc import Iterator
from typing import IO, Final

import httpx
import snappy
import structlog
from prometheus_client import CollectorRegistry, Metric, multiprocess
from prometheus_client.samples import Sample

from rapidly.config import settings
from rapidly.redis import Redis, create_redis
from rapidly.worker._queue_metrics import collect_queue_metrics

_logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Instance identification
# ---------------------------------------------------------------------------

_INSTANCE_LABEL: Final[str] = (
    os.environ.get("RENDER_INSTANCE_ID")
    or os.environ.get("HOSTNAME")
    or socket.gethostname()
)

# ---------------------------------------------------------------------------
# Protobuf helpers — minimal hand-rolled encoders for the Remote Write
# wire format so we avoid pulling in a protobuf dependency.
# ---------------------------------------------------------------------------

_WIRE_VARINT = 0
_WIRE_64BIT = 1
_WIRE_LEN_DELIMITED = 2


def _varint(n: int) -> bytes:
    """Encode a non-negative integer as a protobuf base-128 varint."""
    if n < 0:
        raise ValueError(f"Negative varint unsupported: {n}")
    parts = bytearray()
    while n > 0x7F:
        parts.append((n & 0x7F) | 0x80)
        n >>= 7
    parts.append(n & 0x7F)
    return bytes(parts)


def _field_bytes(tag: int, payload: bytes) -> bytes:
    """Wrap *payload* with a length-delimited protobuf field header."""
    header = bytes([tag << 3 | _WIRE_LEN_DELIMITED])
    return header + _varint(len(payload)) + payload


def _field_string(tag: int, text: str) -> bytes:
    return _field_bytes(tag, text.encode())


def _field_double(tag: int, value: float) -> bytes:
    return bytes([tag << 3 | _WIRE_64BIT]) + struct.pack("<d", value)


def _field_int64(tag: int, value: int) -> bytes:
    return bytes([tag << 3 | _WIRE_VARINT]) + _varint(value)


# ---------------------------------------------------------------------------
# TimeSeries assembly
# ---------------------------------------------------------------------------


def _build_label_pair(name: str, value: str) -> bytes:
    return _field_string(1, name) + _field_string(2, value)


def _build_sample(value: float, ts_ms: int) -> bytes:
    safe_value = value if math.isfinite(value) else 0.0
    return _field_double(1, safe_value) + _field_int64(2, ts_ms)


def _build_timeseries(
    label_pairs: list[tuple[str, str]], value: float, ts_ms: int
) -> bytes:
    body = b"".join(_field_bytes(1, _build_label_pair(k, v)) for k, v in label_pairs)
    body += _field_bytes(2, _build_sample(value, ts_ms))
    return body


def _build_write_request(series: list[bytes]) -> bytes:
    return b"".join(_field_bytes(1, ts) for ts in series)


# ---------------------------------------------------------------------------
# Multi-process metric harvesting
# ---------------------------------------------------------------------------


def _harvest_metrics() -> Iterator[tuple[list[tuple[str, str]], float]]:
    """Yield ``(labels, value)`` for every sample across all worker processes."""
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)

    env_tag = settings.ENV.value if settings.ENV else "unknown"

    metric: Metric
    for metric in registry.collect():
        sample: Sample
        for sample in metric.samples:
            pairs: list[tuple[str, str]] = [
                ("__name__", sample.name),
                ("env", env_tag),
                ("instance", _INSTANCE_LABEL),
            ]
            pairs.extend(sample.labels.items())
            yield pairs, sample.value


# ---------------------------------------------------------------------------
# HTTP push with retries
# ---------------------------------------------------------------------------

_MAX_PUSH_ATTEMPTS: Final[int] = 3


def _send_write_request(
    client: httpx.Client, url: str, auth_headers: dict[str, str]
) -> None:
    """Collect all metrics and POST them as a single Remote Write request."""
    now_ms = int(time.time() * 1000)

    series = [
        _build_timeseries(labels, val, now_ms) for labels, val in _harvest_metrics()
    ]
    if not series:
        return

    payload = snappy.compress(_build_write_request(series))

    for attempt in range(_MAX_PUSH_ATTEMPTS):
        try:
            resp = client.post(
                url,
                content=payload,
                headers={
                    **auth_headers,
                    "Content-Type": "application/x-protobuf",
                    "Content-Encoding": "snappy",
                    "X-Prometheus-Remote-Write-Version": "0.1.0",
                },
            )
            if resp.status_code in {200, 204}:
                return

            if resp.status_code >= 500 and attempt < _MAX_PUSH_ATTEMPTS - 1:
                _logger.warning(
                    "remote_write.retrying",
                    status=resp.status_code,
                    attempt=attempt + 1,
                )
                time.sleep(min(2**attempt, 10))
                continue

            _logger.warning(
                "remote_write.rejected",
                status=resp.status_code,
                body=resp.text[:200],
            )
            return

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt < _MAX_PUSH_ATTEMPTS - 1:
                _logger.warning(
                    "remote_write.retrying",
                    error=str(exc),
                    attempt=attempt + 1,
                )
                time.sleep(min(2**attempt, 10))
                continue
            _logger.error("remote_write.network_failure", error=str(exc))


# ---------------------------------------------------------------------------
# Queue-metrics collection (async, with retry)
# ---------------------------------------------------------------------------


async def _refresh_queue_metrics(redis_conn: Redis) -> None:
    for attempt in range(_MAX_PUSH_ATTEMPTS):
        try:
            await collect_queue_metrics(redis_conn)
            return
        except Exception as exc:
            backoff = min(2**attempt, 10)
            if attempt < _MAX_PUSH_ATTEMPTS - 1:
                _logger.warning(
                    "queue_metrics.retrying",
                    error=str(exc),
                    attempt=attempt + 1,
                    backoff=backoff,
                )
                await asyncio.sleep(backoff)
            else:
                _logger.warning(
                    "queue_metrics.exhausted_retries",
                    error=str(exc),
                    attempts=_MAX_PUSH_ATTEMPTS,
                )


# ---------------------------------------------------------------------------
# Background pusher thread
# ---------------------------------------------------------------------------


def _pusher_loop(
    endpoint: str,
    user: str | None,
    password: str | None,
    interval_sec: int,
    halt: threading.Event,
    *,
    with_queue_metrics: bool = True,
) -> None:
    """Blocking loop that pushes metrics on a fixed cadence."""
    auth_headers: dict[str, str] = {}
    if user and password:
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        auth_headers["Authorization"] = f"Basic {token}"

    event_loop: asyncio.AbstractEventLoop | None = None
    redis_conn: Redis | None = None

    if with_queue_metrics:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        redis_conn = create_redis("worker")

    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as http:
            while not halt.is_set():
                tick = time.monotonic()
                try:
                    if with_queue_metrics and event_loop and redis_conn:
                        event_loop.run_until_complete(
                            _refresh_queue_metrics(redis_conn)
                        )
                    _send_write_request(http, endpoint, auth_headers)
                except Exception as exc:
                    _logger.error(
                        "remote_write.loop_error",
                        error=str(exc),
                        kind=type(exc).__name__,
                        exc_info=True,
                    )
                remaining = max(0, interval_sec - (time.monotonic() - tick))
                if remaining > 0:
                    halt.wait(remaining)
    finally:
        if event_loop and redis_conn:
            event_loop.run_until_complete(redis_conn.close())
            event_loop.close()


# ---------------------------------------------------------------------------
# Lifecycle management (module-level singletons guarded by a lock)
# ---------------------------------------------------------------------------

_guard = threading.Lock()
_thread: threading.Thread | None = None
_halt_event: threading.Event | None = None
_lock_fd: IO[bytes] | None = None


def start_remote_write_pusher(*, include_queue_metrics: bool = True) -> bool:
    """Spawn the background pusher thread if configuration is present.

    Uses a file lock so that only one OS process per host actually
    pushes, avoiding duplicate series when multiple uvicorn workers run.

    Returns ``True`` when the pusher is (or was already) running.
    """
    global _thread, _halt_event, _lock_fd

    with _guard:
        if _thread is not None:
            return True

        url = settings.PROMETHEUS_REMOTE_WRITE_URL
        if not url:
            _logger.info("remote_write.disabled", reason="no URL configured")
            return False

        push_interval = settings.PROMETHEUS_REMOTE_WRITE_INTERVAL
        if push_interval <= 0:
            _logger.error("remote_write.bad_config", reason="interval must be > 0")
            return False

        # Acquire an exclusive file lock so sibling processes skip pushing.
        lock_path = settings.WORKER_PROMETHEUS_DIR / ".pusher.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _lock_fd = open(lock_path, "wb")
            fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError):
            _logger.info("remote_write.skipped", reason="lock held by another process")
            if _lock_fd:
                _lock_fd.close()
                _lock_fd = None
            return False

        _halt_event = threading.Event()
        _thread = threading.Thread(
            target=_pusher_loop,
            args=(
                url,
                settings.PROMETHEUS_REMOTE_WRITE_USERNAME,
                settings.PROMETHEUS_REMOTE_WRITE_PASSWORD,
                push_interval,
                _halt_event,
            ),
            kwargs={"with_queue_metrics": include_queue_metrics},
            daemon=True,
            name="rapidly-remote-write",
        )
        _thread.start()
        _logger.info("remote_write.started", url=url, interval_sec=push_interval)
        return True


def stop_remote_write_pusher(timeout: float = 5.0) -> None:
    """Signal the pusher thread to stop and wait for it to finish."""
    global _thread, _halt_event, _lock_fd

    with _guard:
        if _thread is None or _halt_event is None:
            return
        _logger.info("remote_write.stopping")
        _halt_event.set()
        ref = _thread

    ref.join(timeout=timeout)

    with _guard:
        if ref.is_alive():
            _logger.warning("remote_write.stop_timed_out")
        else:
            _logger.info("remote_write.stopped")

        _thread = None
        _halt_event = None

        if _lock_fd:
            try:
                fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_UN)
                _lock_fd.close()
            except OSError:
                pass
            _lock_fd = None
