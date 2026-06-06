"""Scheduled member-session maintenance: prune expired sessions.

Mirrors ``auth/workers.py`` + ``customer_session/workers.py``.
The ``delete_expired`` action + query have existed on
``MemberSession`` for a while (see actions.py:111,
queries.py:51) but were never wired into a cron actor —
so expired member-session rows accumulated forever.
"""

import structlog

from rapidly.logging import Logger
from rapidly.worker import AsyncSessionMaker, CronTrigger, TaskPriority, actor

from .actions import member_session as member_session_service

_log: Logger = structlog.get_logger(__name__)

# Midnight UTC — same daily cadence as the other identity-
# cleanup actors so all of this work concentrates in the
# off-peak window.
_CLEANUP_HOUR: int = 0
_CLEANUP_MINUTE: int = 0


@actor(
    actor_name="member_session.delete_expired",
    cron_trigger=CronTrigger(hour=_CLEANUP_HOUR, minute=_CLEANUP_MINUTE),
    priority=TaskPriority.LOW,
    max_retries=0,
)
async def member_session_delete_expired() -> None:
    """Remove expired member sessions."""
    async with AsyncSessionMaker() as session:
        await member_session_service.delete_expired(session)
        _log.info("member_session.expired_cleanup")
