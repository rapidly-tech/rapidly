"""Background tasks for file sharing audit trail, webhooks, and notifications."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from apscheduler.triggers.cron import CronTrigger

from rapidly.core.utils import now_utc
from rapidly.models.webhook_endpoint import WebhookEventType
from rapidly.worker import AsyncSessionMaker, TaskPriority, actor, dispatch_task

from .pg_repository import FileShareSessionRepository

if TYPE_CHECKING:
    from rapidly.messaging.notifications.notification import NotificationType

_log = structlog.get_logger(__name__)


# ── Notification helpers ──


async def _send_file_sharing_notification(
    session_id: UUID,
    notification_type: NotificationType,
    build_payload: Callable[[Any, str], Any],
) -> None:
    """Load a file share session and send a notification to the session owner."""
    from rapidly.messaging.notifications import actions as notification_service
    from rapidly.messaging.notifications.actions import PartialNotification

    async with AsyncSessionMaker() as session:
        repo = FileShareSessionRepository.from_session(session)
        fs_session = await repo.get_by_id(session_id)
        if fs_session is None or fs_session.user_id is None:
            return

        file_name = fs_session.file_name or fs_session.title or "Untitled file"
        payload = build_payload(fs_session, file_name)

        await notification_service.send_to_user(
            session,
            user_id=fs_session.user_id,
            notif=PartialNotification(
                type=notification_type,
                payload=payload,
            ),
        )


def _build_download_completed_payload(fs_session: Any, file_name: str) -> Any:
    from rapidly.messaging.notifications.notification import (
        FileShareDownloadCompletedNotificationPayload,
    )

    return FileShareDownloadCompletedNotificationPayload(file_name=file_name)


def _build_session_expired_payload(fs_session: Any, file_name: str) -> Any:
    from rapidly.messaging.notifications.notification import (
        FileShareSessionExpiredNotificationPayload,
    )

    return FileShareSessionExpiredNotificationPayload(file_name=file_name)


# ── Expiry ──


async def _send_file_sharing_webhook(session_id: UUID, event: WebhookEventType) -> None:
    """Load a file share session and send webhook if org-scoped."""
    from rapidly.messaging.webhook import actions as webhook_service
    from rapidly.platform.workspace.queries import WorkspaceRepository

    async with AsyncSessionMaker() as session:
        repo = FileShareSessionRepository.from_session(session)
        fs_session = await repo.get_by_id(session_id)
        if fs_session is None:
            _log.warning(
                "File share session not found for webhook",
                extra={"file_share_session_id": str(session_id), "event": event},
            )
            return

        if fs_session.workspace_id is None:
            return

        org_repo = WorkspaceRepository.from_session(session)
        workspace = await org_repo.get_by_id(fs_session.workspace_id)
        if workspace is None:
            return

        await webhook_service.send(
            session,
            target=workspace,
            event=event,
            data=fs_session,
        )


@actor(actor_name="file_sharing.session_created", priority=TaskPriority.LOW)
async def file_sharing_session_created(file_share_session_id: UUID) -> None:
    """Process a newly created file sharing session and send webhook."""
    await _send_file_sharing_webhook(
        file_share_session_id,
        WebhookEventType.file_sharing_session_created,
    )


@actor(actor_name="file_sharing.download_completed", priority=TaskPriority.LOW)
async def file_sharing_download_completed(file_share_session_id: UUID) -> None:
    """Process a completed download event — send webhook and notification."""
    await _send_file_sharing_webhook(
        file_share_session_id,
        WebhookEventType.file_sharing_session_download_completed,
    )
    from rapidly.messaging.notifications.notification import NotificationType as _NT

    await _send_file_sharing_notification(
        file_share_session_id,
        _NT.file_share_download_completed,
        _build_download_completed_payload,
    )


@actor(actor_name="file_sharing.session_expired", priority=TaskPriority.LOW)
async def file_sharing_session_expired(file_share_session_id: UUID) -> None:
    """Process an expired file sharing session — send webhook and notification."""
    await _send_file_sharing_webhook(
        file_share_session_id,
        WebhookEventType.file_sharing_session_expired,
    )
    from rapidly.messaging.notifications.notification import NotificationType as _NT

    await _send_file_sharing_notification(
        file_share_session_id,
        _NT.file_share_session_expired,
        _build_session_expired_payload,
    )


# ── Cleanup ──


@actor(
    actor_name="file_sharing.check_expired_sessions",
    priority=TaskPriority.LOW,
    cron_trigger=CronTrigger(minute="*/5"),
    max_retries=0,
)
async def file_sharing_check_expired_sessions() -> None:
    """Cron task: transition expired sessions to expired status.

    Runs every 5 minutes to find sessions past their expires_at
    that are still in created/active status, and marks them expired.
    """
    async with AsyncSessionMaker() as session:
        repo = FileShareSessionRepository.from_session(session)
        expired_ids = await repo.expire_active_sessions(now_utc())

        if not expired_ids:
            return

        _log.info("Expired %d file share sessions", len(expired_ids))

        for session_id in expired_ids:
            dispatch_task(
                "file_sharing.session_expired",
                file_share_session_id=session_id,
            )
