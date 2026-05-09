"""User session persistence layer.

``UserSessionRepository`` handles look-ups and clean-up for
browser-backed sessions stored against hashed cookie tokens.
"""

from uuid import UUID

from sqlalchemy import delete, func, select

from rapidly.config import settings
from rapidly.core.crypto import get_token_hash
from rapidly.core.queries import Repository
from rapidly.core.utils import now_utc
from rapidly.models import UserSession


class UserSessionRepository(Repository[UserSession]):
    """CRUD and token-based look-ups for user sessions."""

    model = UserSession

    # ── Reads ──

    async def get_by_token(
        self,
        token: str,
        *,
        include_expired: bool = False,
    ) -> UserSession | None:
        """Resolve a raw cookie token to its session, optionally including expired ones."""
        token_hash = get_token_hash(token, secret=settings.SECRET)
        stmt = select(UserSession).where(UserSession.token == token_hash)
        if not include_expired:
            stmt = stmt.where(UserSession.expires_at > now_utc())
        return await self.get_one_or_none(stmt)

    async def count_active_for_user(self, user_id: UUID) -> int:
        """Count non-expired sessions for a user."""
        stmt = (
            select(func.count())
            .select_from(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.expires_at > now_utc(),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    # ── Writes ──

    async def delete_expired(self) -> None:
        """Remove all sessions whose expiry has passed."""
        await self.session.execute(
            delete(UserSession).where(UserSession.expires_at < now_utc())
        )

    async def evict_oldest_for_user(self, user_id: UUID, keep: int) -> None:
        """Delete the oldest sessions for a user, keeping only the *keep* most recent."""
        keep_ids = (
            select(UserSession.id)
            .where(
                UserSession.user_id == user_id,
                UserSession.expires_at > now_utc(),
            )
            .order_by(UserSession.created_at.desc())
            .limit(keep)
        )
        await self.session.execute(
            delete(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.id.not_in(keep_ids),
                UserSession.expires_at > now_utc(),
            )
        )
