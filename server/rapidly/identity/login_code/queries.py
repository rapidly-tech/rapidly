"""Login code persistence layer.

``LoginCodeRepository`` handles token-hash lookups for the one-time
login code authentication flow.
"""

from sqlalchemy import func, select
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
        """Find a non-expired login code matching the given hash and email.

        Email comparison is case-insensitive: ``request`` stores the
        address verbatim as the caller typed it, but a user who
        requested with ``Alice@example.com`` and verifies with
        ``alice@example.com`` should still be able to sign in.  The
        ``code_hash`` already proves possession of the code; the
        email is just the second factor that the code belongs to a
        specific address.
        """
        stmt = (
            select(LoginCode)
            .where(
                LoginCode.code_hash == code_hash,
                func.lower(LoginCode.email) == email.lower(),
                LoginCode.expires_at > now_utc(),
            )
            .options(joinedload(LoginCode.user))
        )
        return await self.get_one_or_none(stmt)
