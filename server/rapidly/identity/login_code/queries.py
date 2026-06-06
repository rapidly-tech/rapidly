"""Login code persistence layer.

``LoginCodeRepository`` handles token-hash lookups for the one-time
login code authentication flow.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from rapidly.core.queries import Repository
from rapidly.core.utils import now_utc
from rapidly.models import LoginCode


class LoginCodeRepository(Repository[LoginCode]):
    """Login code queries: valid-code lookup by hash and email."""

    model = LoginCode

    # ── Reads ──

    async def get_valid_by_hash_and_email(
        self, code_hash: str, email: str
    ) -> LoginCode | None:
        """Find a non-expired login code matching the given hash and email."""
        stmt = (
            select(LoginCode)
            .where(
                LoginCode.code_hash == code_hash,
                LoginCode.email == email,
                LoginCode.expires_at > now_utc(),
            )
            .options(joinedload(LoginCode.user))
        )
        return await self.get_one_or_none(stmt)

    # ── Writes ──

    async def delete_expired(self) -> None:
        """Remove all login codes whose expiry has passed.

        Lookups already filter on ``expires_at > now()`` so stale
        rows are inert from an auth-correctness perspective, but
        they accumulate forever on the table (the success path
        ``delete``s the matched row on redemption; expired-but-
        never-redeemed rows linger). This periodic cleanup keeps
        the table bounded — same pattern as
        ``UserSessionRepository.delete_expired``.
        """
        await self.session.execute(
            delete(LoginCode).where(LoginCode.expires_at < now_utc())
        )
