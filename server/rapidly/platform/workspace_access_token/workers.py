"""Background tasks for workspace access token usage tracking
+ daily expired-token cleanup."""

import uuid
from datetime import UTC, datetime

import structlog

from rapidly.logging import Logger
from rapidly.worker import AsyncSessionMaker, CronTrigger, TaskPriority, actor

from . import actions as workspace_access_token_service
from .queries import WorkspaceAccessTokenRepository

_log: Logger = structlog.get_logger(__name__)

# Midnight UTC — same daily cadence as the auth / member-session
# / login-code / customer-session-code cleanup actors. Keeping
# all identity-cleanup work in one off-peak window.
_CLEANUP_HOUR: int = 0
_CLEANUP_MINUTE: int = 0


def _record_usage_debounce_key(
    workspace_access_token_id: uuid.UUID, last_used_at: float
) -> str:
    return f"workspace_access_token.record_usage:{workspace_access_token_id}"


@actor(
    actor_name="workspace_access_token.record_usage",
    priority=TaskPriority.LOW,
    max_retries=1,
    min_backoff=5_000,
    debounce_key=_record_usage_debounce_key,
)
async def record_usage(
    workspace_access_token_id: uuid.UUID, last_used_at: float
) -> None:
    async with AsyncSessionMaker() as session:
        repository = WorkspaceAccessTokenRepository.from_session(session)
        await repository.record_usage(
            workspace_access_token_id, datetime.fromtimestamp(last_used_at, tz=UTC)
        )


@actor(
    actor_name="workspace_access_token.soft_delete_expired",
    cron_trigger=CronTrigger(hour=_CLEANUP_HOUR, minute=_CLEANUP_MINUTE),
    priority=TaskPriority.LOW,
    max_retries=0,
)
async def workspace_access_token_soft_delete_expired() -> None:
    """Soft-delete tokens whose expiry has passed.

    Conservative — soft-delete (not hard-delete) so the row
    survives for audit. The lookup path already rejects
    expired tokens; this keeps the operator-visible list +
    count_by_workspace tidy.
    """
    async with AsyncSessionMaker() as session:
        rowcount = await workspace_access_token_service.soft_delete_expired(session)
        if rowcount:
            _log.info(
                "workspace_access_token.expired_cleanup",
                soft_deleted=rowcount,
            )
