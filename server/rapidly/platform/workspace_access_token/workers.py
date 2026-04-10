"""Background tasks for workspace access token usage tracking."""

import uuid
from datetime import UTC, datetime

from rapidly.worker import AsyncSessionMaker, TaskPriority, actor

from .queries import WorkspaceAccessTokenRepository


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
