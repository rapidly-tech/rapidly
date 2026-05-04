"""Event-stream pub/sub service backed by Redis.

Manages channel subscriptions and message broadcasting for the SSE
endpoints, translating domain events into serialised payloads
published on per-workspace Redis channels.
"""

from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel

from rapidly.logging import Logger
from rapidly.redis import Redis

_log: Logger = structlog.get_logger()


# ── Channel management ──


class Receivers(BaseModel):
    user_id: UUID | None = None
    workspace_id: UUID | None = None
    customer_id: UUID | None = None

    def generate_channel_name(self, scope: str, resource_id: UUID | str) -> str:
        return f"{scope}:{resource_id}"

    def get_channels(self) -> list[str]:
        channels = []
        if self.user_id:
            channels.append(self.generate_channel_name("user", self.user_id))

        if self.workspace_id:
            channels.append(self.generate_channel_name("org", self.workspace_id))

        if self.customer_id:
            channels.append(self.generate_channel_name("customer", self.customer_id))

        return channels


class Event(BaseModel):
    id: UUID
    key: str
    payload: dict[str, Any]


# ── Pub/Sub ──


async def send_event(redis: Redis, event_json: str, channels: list[str]) -> None:
    for channel in channels:
        await redis.publish(channel, event_json)
    _log.debug(
        "Published event to eventstream", event_json=event_json, channels=channels
    )
