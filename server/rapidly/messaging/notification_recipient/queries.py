"""Notification-recipient persistence layer.

Handles user-scoped device registration lookups, push-token-based
de-duplication queries, and soft-delete of notification recipients.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.core.queries import (
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
)
from rapidly.core.queries.base import Options
from rapidly.models.notification_recipient import NotificationRecipient

from .types import NotificationRecipientPlatform


class NotificationRecipientRepository(
    SoftDeleteByIdMixin[NotificationRecipient, UUID],
    SoftDeleteMixin[NotificationRecipient],
    Repository[NotificationRecipient],
):
    """Push-token registration queries with deduplication and soft-delete."""

    model = NotificationRecipient

    # ------------------------------------------------------------------
    # Token lookup
    # ------------------------------------------------------------------

    async def get_by_expo_token(
        self, expo_push_token: str
    ) -> NotificationRecipient | None:
        stmt = self.get_base_statement().where(
            NotificationRecipient.expo_push_token == expo_push_token
        )
        return await self.get_one_or_none(stmt)

    # ------------------------------------------------------------------
    # User-scoped queries
    # ------------------------------------------------------------------

    async def list_by_user(
        self,
        user_id: UUID,
        platform: NotificationRecipientPlatform | None,
        expo_push_token: str | None,
        *,
        options: Options = (),
    ) -> Sequence[NotificationRecipient]:
        stmt = self.get_base_statement().where(NotificationRecipient.user_id == user_id)

        if expo_push_token:
            stmt = stmt.where(NotificationRecipient.expo_push_token == expo_push_token)

        if platform:
            stmt = stmt.where(NotificationRecipient.platform == platform)

        return await self.get_all(stmt.options(*options))

    # ------------------------------------------------------------------
    # Removal
    # ------------------------------------------------------------------

    async def delete_for_user(
        self, notification_recipient_id: UUID, user_id: UUID, *, flush: bool = False
    ) -> None:
        stmt = (
            self.get_base_statement()
            .where(NotificationRecipient.id == notification_recipient_id)
            .where(NotificationRecipient.user_id == user_id)
        )
        recipient = await self.get_one_or_none(stmt)

        if recipient:
            await self.soft_delete(recipient, flush=flush)

        return None
