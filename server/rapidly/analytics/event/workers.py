"""Background tasks for event ingestion.

Dispatched after raw events are written; performs fan-out to
webhook delivery, analytics aggregation, etc.
"""

import uuid
from collections.abc import Sequence

from rapidly.worker import AsyncSessionMaker, TaskPriority, actor

from . import actions as event_actions

_ACTOR_NAME = "event.ingested"
_MAX_RETRIES = 5
_MIN_BACKOFF_MS = 30_000


@actor(
    actor_name=_ACTOR_NAME,
    priority=TaskPriority.LOW,
    max_retries=_MAX_RETRIES,
    min_backoff=_MIN_BACKOFF_MS,
)
async def event_ingested(event_ids: Sequence[uuid.UUID]) -> None:
    async with AsyncSessionMaker() as session:
        await event_actions.ingested(session, event_ids)
