"""Scheduled task: purge expired customer sessions.

Runs once daily at midnight to remove sessions whose TTL has passed,
keeping the session table lean. Shape mirrors the auth /
login_code / member_session / customer_session_code /
workspace_access_token cleanup actors so all 6 identity /
customer cleanup workers share the same _CLEANUP_HOUR /
_CLEANUP_MINUTE constants + log-info shape.
"""

import structlog

from rapidly.logging import Logger
from rapidly.worker import AsyncSessionMaker, CronTrigger, TaskPriority, actor

from . import actions as session_actions

_log: Logger = structlog.get_logger(__name__)

# Midnight UTC — same daily cadence as the rest of the
# identity / customer cleanup actors so off-peak work
# concentrates in one window.
_CLEANUP_HOUR: int = 0
_CLEANUP_MINUTE: int = 0


@actor(
    actor_name="customer_session.delete_expired",
    cron_trigger=CronTrigger(hour=_CLEANUP_HOUR, minute=_CLEANUP_MINUTE),
    priority=TaskPriority.LOW,
    max_retries=0,
)
async def customer_session_delete_expired() -> None:
    async with AsyncSessionMaker() as session:
        await session_actions.customer_session.delete_expired(session)
        _log.info("customer_session.expired_cleanup")
