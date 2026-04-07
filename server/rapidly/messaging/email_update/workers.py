"""Scheduled task: clean up expired email-update records.

Runs once daily at midnight to purge stale verification rows.
"""

import structlog

from rapidly.worker import AsyncSessionMaker, CronTrigger, TaskPriority, actor

from .actions import email_update as email_update_actions

_log = structlog.get_logger(__name__)

_CRON_MIDNIGHT = CronTrigger(hour=0, minute=0)


@actor(
    actor_name="email_update.delete_expired_record",
    cron_trigger=_CRON_MIDNIGHT,
    priority=TaskPriority.LOW,
    max_retries=0,
)
async def email_update_delete_expired_record() -> None:
    _log.info("email_update.cleanup_start")
    async with AsyncSessionMaker() as session:
        await email_update_actions.delete_expired_record(session)
    _log.info("email_update.cleanup_done")
