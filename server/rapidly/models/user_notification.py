"""Per-user notification read cursor.

Stores the ID of the last notification the user has seen so the UI
can compute an unread count without per-notification read flags.
"""

from uuid import UUID

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from rapidly.core.db.models import Model


class UserNotification(Model):
    """Tracks per-user notification read state via a high-water-mark ID."""

    __tablename__ = "user_notifications"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        primary_key=True,
    )

    last_read_notification_id: Mapped[UUID] = mapped_column(Uuid, nullable=True)
