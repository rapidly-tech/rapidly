"""Scheduled task: clean up expired email-update records.

Runs once daily at midnight to purge stale verification rows.
Shares the ``_CLEANUP_HOUR`` / ``_CLEANUP_MINUTE`` constants
with the rest of the identity / customer cleanup actors so
the cron-schedule pin is consistent across the family.
"""

import structlog

from rapidly.worker import AsyncSessionMaker, CronTrigger, TaskPriority, actor

from .actions import email_update as email_update_actions

_log = structlog.get_logger(__name__)

# Midnight UTC — same off-peak window as the 6 other
# identity / customer cleanup actors. Kept as constants
# (not inline ``CronTrigger(hour=0)``) so test_workers can
# import + pin them without parsing the actor decorator.
_CLEANUP_HOUR: int = 0
_CLEANUP_MINUTE: int = 0


@actor(
    actor_name="email_update.delete_expired_record",
    cron_trigger=CronTrigger(hour=_CLEANUP_HOUR, minute=_CLEANUP_MINUTE),
    priority=TaskPriority.LOW,
    max_retries=0,
)
async def email_update_delete_expired_record() -> None:
    # Pre-existing log shape: this actor logs both start +
    # done events (vs. the single-event shape used by the
    # other 6 cleanup actors). Kept as-is to avoid breaking
    # any log-grep tooling that keys off these specific event
    # names.
    _log.info("email_update.cleanup_start")
    async with AsyncSessionMaker() as session:
        await email_update_actions.delete_expired_record(session)
    _log.info("email_update.cleanup_done")
