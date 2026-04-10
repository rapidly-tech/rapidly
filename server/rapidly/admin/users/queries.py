"""Admin user query repository.

Centralises direct DB access for the admin users module, following the
convention that API handlers never execute raw ``select()`` /
``session.execute()`` calls themselves.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.queries import Repository
from rapidly.models.user import OAuthAccount


class AdminUserRepository(Repository[OAuthAccount]):
    """Admin-specific OAuth account queries for the user detail view."""

    model = OAuthAccount

    async def get_active_oauth_accounts(self, user_id: UUID) -> Sequence[OAuthAccount]:
        """Return all active (non-deleted) OAuth accounts for a user."""
        stmt = select(OAuthAccount).where(
            OAuthAccount.user_id == user_id,
            OAuthAccount.deleted_at.is_(None),
        )
        return await self.get_all(stmt)

    async def get_deleted_oauth_accounts(self, user_id: UUID) -> Sequence[OAuthAccount]:
        """Return all soft-deleted OAuth accounts for a user."""
        stmt = select(OAuthAccount).where(
            OAuthAccount.user_id == user_id,
            OAuthAccount.deleted_at.is_not(None),
        )
        return await self.get_all(stmt)
