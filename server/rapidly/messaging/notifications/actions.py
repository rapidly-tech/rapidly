"""In-app notification delivery, read-state tracking, and org-wide fan-out."""

from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, TypeAdapter

from rapidly.models.notification import Notification
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.worker import dispatch_task

from .notification import Notification as NotificationSchema
from .notification import NotificationPayload, NotificationType
from .queries import NotificationRepository

_MAX_USER_NOTIFICATIONS: int = 100

_notification_adapter: TypeAdapter[NotificationSchema] = TypeAdapter(NotificationSchema)


class PartialNotification(BaseModel):
    """Lightweight input for creating a notification (type + payload only)."""

    type: NotificationType
    payload: NotificationPayload


# ── Reads ─────────────────────────────────────────────────────────


async def get(session: AsyncSession, id: UUID) -> Notification | None:
    repo = NotificationRepository.from_session(session)
    return await repo.get_by_id(id)


async def get_for_user(
    session: AsyncReadSession, user_id: UUID
) -> Sequence[Notification]:
    repo = NotificationRepository.from_session(session)
    return await repo.list_for_user(user_id, limit=_MAX_USER_NOTIFICATIONS)


# ── Sends ─────────────────────────────────────────────────────────


async def send_to_user(
    session: AsyncSession,
    user_id: UUID,
    notif: PartialNotification,
) -> bool:
    repo = NotificationRepository.from_session(session)
    record = Notification(
        user_id=user_id,
        type=notif.type,
        payload=notif.payload.model_dump(mode="json"),
    )
    await repo.create(record, flush=True)

    dispatch_task("notifications.send", notification_id=record.id)
    dispatch_task("notifications.push", notification_id=record.id)
    return True


# ── Payload parsing ───────────────────────────────────────────────


def parse_payload(n: Notification) -> NotificationPayload:
    return _notification_adapter.validate_python(n).payload


# ── Read-cursor ───────────────────────────────────────────────────


async def get_user_last_read(session: AsyncReadSession, user_id: UUID) -> UUID | None:
    repo = NotificationRepository.from_session(session)
    return await repo.get_user_last_read(user_id)


async def set_user_last_read(
    session: AsyncSession, user_id: UUID, notification_id: UUID
) -> None:
    repo = NotificationRepository.from_session(session)
    await repo.set_user_last_read(user_id, notification_id)
