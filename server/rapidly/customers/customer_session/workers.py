"""Scheduled task: purge expired customer sessions.

Runs once daily at midnight to remove sessions whose TTL has passed,
keeping the session table lean.
"""

from rapidly.worker import AsyncSessionMaker, CronTrigger, TaskPriority, actor

from . import actions as session_actions

_CRON_MIDNIGHT = CronTrigger(hour=0, minute=0)


@actor(
    actor_name="customer_session.delete_expired",
    cron_trigger=_CRON_MIDNIGHT,
    priority=TaskPriority.LOW,
    max_retries=0,
)
async def customer_session_delete_expired() -> None:
    async with AsyncSessionMaker() as session:
        await session_actions.customer_session.delete_expired(session)
