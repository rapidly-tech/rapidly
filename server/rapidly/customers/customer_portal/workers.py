"""Scheduled customer-portal maintenance.

Currently: prune expired CustomerSessionCode rows. The
``delete_expired`` query + action have always existed (the
lookup path filters on ``expires_at > now()``) but no cron
actor invoked them, so expired OTP codes accumulated
forever on ``customer_session_codes``.

Mirrors ``auth/workers.py`` / ``customer_session/workers.py``
/ ``identity/login_code/workers.py`` / ``identity/member_
session/workers.py``.
"""

import structlog

from rapidly.logging import Logger
from rapidly.worker import AsyncSessionMaker, CronTrigger, TaskPriority, actor

from .actions.customer_session import customer_session as customer_session_service

_log: Logger = structlog.get_logger(__name__)

# Midnight UTC — same daily cadence as the other identity-
# adjacent cleanup actors so all of this work concentrates
# in one off-peak window.
_CLEANUP_HOUR: int = 0
_CLEANUP_MINUTE: int = 0


@actor(
    actor_name="customer_session_code.delete_expired",
    cron_trigger=CronTrigger(hour=_CLEANUP_HOUR, minute=_CLEANUP_MINUTE),
    priority=TaskPriority.LOW,
    max_retries=0,
)
async def customer_session_code_delete_expired() -> None:
    """Remove expired customer session codes (OTP)."""
    async with AsyncSessionMaker() as session:
        await customer_session_service.delete_expired_codes(session)
        _log.info("customer_session_code.expired_cleanup")
