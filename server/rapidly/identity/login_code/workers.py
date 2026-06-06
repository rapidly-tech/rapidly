"""Scheduled login-code maintenance: prune expired codes.

Mirrors the auth/workers.py pattern. Codes are short-lived
(see ``settings.LOGIN_CODE_TTL_SECONDS``) — lookups already
filter on ``expires_at > now()`` so stale rows are inert from
an auth-correctness perspective, but they accumulate forever
on the table because only the success path deletes the row
(on redemption). This periodic cleanup keeps the table bounded.
"""

import structlog

from rapidly.logging import Logger
from rapidly.worker import AsyncSessionMaker, CronTrigger, TaskPriority, actor

from . import actions as login_code_service

_log: Logger = structlog.get_logger(__name__)

# Midnight UTC — same daily cadence the auth sessions use so
# all identity-cleanup work concentrates in the off-peak hour.
_CLEANUP_HOUR: int = 0
_CLEANUP_MINUTE: int = 0


@actor(
    actor_name="login_code.delete_expired",
    cron_trigger=CronTrigger(hour=_CLEANUP_HOUR, minute=_CLEANUP_MINUTE),
    priority=TaskPriority.LOW,
    max_retries=0,
)
async def login_code_delete_expired() -> None:
    """Remove expired login codes."""
    async with AsyncSessionMaker() as session:
        await login_code_service.delete_expired(session)
        _log.info("login_code.expired_cleanup")
