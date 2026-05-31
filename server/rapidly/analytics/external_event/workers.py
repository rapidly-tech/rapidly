"""Background task definitions for external event processing."""

from datetime import timedelta

from apscheduler.triggers.cron import CronTrigger

from rapidly.core.utils import now_utc
from rapidly.worker import AsyncSessionMaker, TaskPriority, actor

from .queries import ExternalEventRepository

# Schedule constant — exposed so tests can pin the slot. Matches the
# normalized shape used by customer_session + email_update workers.
_CRON_MIDNIGHT = CronTrigger(hour=0, minute=0)


@actor(
    actor_name="external_event.prune",
    priority=TaskPriority.LOW,
    cron_trigger=_CRON_MIDNIGHT,
    max_retries=0,
)
async def external_event_prune() -> None:
    async with AsyncSessionMaker() as session:
        repository = ExternalEventRepository.from_session(session)
        await repository.delete_before(now_utc() - timedelta(days=30))
