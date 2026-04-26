"""Notification list and mark-read request/response models."""

from pydantic import UUID4

from rapidly.core.types import Schema
from rapidly.messaging.notifications.notification import Notification


class NotificationsMarkRead(Schema):
    notification_id: UUID4


class NotificationsList(Schema):
    notifications: list[Notification]
    last_read_notification_id: UUID4 | None
