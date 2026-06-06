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

        Case-insensitive on email: mirrors ``UserRepository.get_by_email``
        (``func.lower(...) == email.lower()``). Without this, a user who
        types ``John@Example.com`` on the login form but later clicks a
        magic link where the URL was lowercased (or vice-versa) would
        fail to authenticate even though both addresses canonically
        resolve to the same RFC-5321 mailbox.
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
