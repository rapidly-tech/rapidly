"""Prometheus gauge exporter for Dramatiq queue depths.

Periodically reads Redis queue lengths and publishes them as
Prometheus ``Gauge`` metrics so that queue back-pressure is visible
in Grafana dashboards.
"""

import json
import time

import structlog
from prometheus_client import Gauge
from redis import RedisError

import rapidly.observability.metrics  # noqa: F401  # Sets PROMETHEUS_MULTIPROC_DIR
from rapidly.logging import Logger
from rapidly.redis import Redis

from ._queues import TaskQueue

_log: Logger = structlog.get_logger()

QUEUE_NAMES = {queue.value for queue in TaskQueue}

QUEUE_SIZE = Gauge(
    "rapidly_queue_size",
    "Number of messages in the queue",
    ["queue"],
    multiprocess_mode="mostrecent",
)

QUEUE_OLDEST_MESSAGE_AGE = Gauge(
    "rapidly_queue_oldest_message_age_seconds",
    "Age of the oldest message in the queue in seconds",
    ["queue"],
    multiprocess_mode="mostrecent",
)


async def collect_queue_metrics(redis: Redis) -> None:
    current_time = time.time()

    for queue_name in QUEUE_NAMES:
        queue_key = f"dramatiq:{queue_name}"
        try:
            queue_size = await redis.llen(queue_key)
        except RedisError as e:
            _log.warning(
                "failed_to_get_queue_size", queue_name=queue_name, error=str(e)
            )
            queue_size = 0

        QUEUE_SIZE.labels(queue=queue_name).set(queue_size)

    for queue_name in QUEUE_NAMES:
        queue_key = f"dramatiq:{queue_name}"
        msgs_key = f"dramatiq:{queue_name}.msgs"
        age_seconds = 0.0

        try:
            queue_size = await redis.llen(queue_key)
            if queue_size > 0:
                oldest_message_id = await redis.lindex(queue_key, 0)
                if oldest_message_id:
                    message_data = await redis.hget(msgs_key, oldest_message_id)
                    if message_data:
                        try:
                            message = json.loads(message_data)
                            if not isinstance(message, dict):
                                _log.warning(
                                    "invalid_message_format",
                                    queue_name=queue_name,
                                    message_type=type(message).__name__,
                                )
                            else:
                                message_timestamp = message.get(
                                    "message_timestamp"
                                ) or message.get("options", {}).get("eta")
                                if message_timestamp:
                                    message_timestamp_seconds = message_timestamp / 1000
                                    age_seconds = max(
                                        0, current_time - message_timestamp_seconds
                                    )
                        except (json.JSONDecodeError, TypeError) as e:
                            _log.warning(
                                "failed_to_parse_message",
                                queue_name=queue_name,
                                error=str(e),
                            )
        except RedisError as e:
            _log.warning("failed_to_get_queue_age", queue_name=queue_name, error=str(e))

        QUEUE_OLDEST_MESSAGE_AGE.labels(queue=queue_name).set(age_seconds)
