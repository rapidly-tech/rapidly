"""Scheduled auth maintenance: prune expired sessions and tokens."""

import structlog

from rapidly.logging import Logger
from rapidly.worker import AsyncSessionMaker, CronTrigger, TaskPriority, actor

from . import actions as auth_service

_log: Logger = structlog.get_logger(__name__)

# Midnight UTC — sessions are cleaned up once per day.
_CLEANUP_HOUR: int = 0
_CLEANUP_MINUTE: int = 0


@actor(
    actor_name="auth.delete_expired",
    cron_trigger=CronTrigger(hour=_CLEANUP_HOUR, minute=_CLEANUP_MINUTE),
    priority=TaskPriority.LOW,
    max_retries=0,
)
async def auth_delete_expired() -> None:
    """Remove expired sessions, tokens, and authorization codes."""
    async with AsyncSessionMaker() as session:
        await auth_service.delete_expired(session)
        _log.info("auth.expired_cleanup")
