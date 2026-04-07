"""Notification persistence layer.

``NotificationRepository`` handles notification lookups and read-cursor
management via the ``UserNotification`` upsert pattern.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from rapidly.core.extensions.sqlalchemy import sql
from rapidly.core.queries import Repository
from rapidly.models.notification import Notification
from rapidly.models.user_notification import UserNotification


class NotificationRepository(Repository[Notification]):
    """Notification queries: by-id, per-user listing, and read-cursor tracking."""

    model = Notification

    # ── Reads ──

    async def get_by_id(self, id: UUID) -> Notification | None:
        stmt = (
            sql.select(Notification)
            .where(Notification.id == id)
            .options(joinedload(Notification.user))
        )
        return await self.get_one_or_none(stmt)

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 100
    ) -> Sequence[Notification]:
        stmt = (
            sql.select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(desc(Notification.created_at))
            .limit(limit)
        )
        return await self.get_all(stmt)

    # ── Read-cursor ──

    async def get_user_last_read(self, user_id: UUID) -> UUID | None:
        stmt = sql.select(UserNotification).where(UserNotification.user_id == user_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return row.last_read_notification_id if row else None

    async def set_user_last_read(self, user_id: UUID, notification_id: UUID) -> None:
        stmt = (
            sql.insert(UserNotification)
            .values(user_id=user_id, last_read_notification_id=notification_id)
            .on_conflict_do_update(
                index_elements=[UserNotification.user_id],
                set_={"last_read_notification_id": notification_id},
            )
        )
        await self.session.execute(stmt)
