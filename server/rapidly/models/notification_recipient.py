"""Push notification recipient: a registered device endpoint for a user."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .user import User


class NotificationRecipient(BaseEntity):
    """A device registered to receive push notifications via Expo.

    The composite unique index on (user_id, expo_push_token, deleted_at)
    prevents duplicate registrations while allowing the same token to be
    re-registered after soft-deletion.
    """

    __tablename__ = "notification_recipients"
    __table_args__ = (
        Index(
            "ix_notification_recipients_expo_push_token",
            "user_id",
            "expo_push_token",
            "deleted_at",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    # -- Owner ---------------------------------------------------------------

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="cascade")
    )

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise_on_sql")

    # -- Device details ------------------------------------------------------

    platform: Mapped[str] = mapped_column(String, nullable=False)
    expo_push_token: Mapped[str] = mapped_column(String, nullable=False)
