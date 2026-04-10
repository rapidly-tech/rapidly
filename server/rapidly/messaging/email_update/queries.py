"""Email verification persistence layer.

``EmailVerificationRepository`` handles token-hash lookups and
expired-record cleanup for the email-change verification flow.
"""

from sqlalchemy import delete
from sqlalchemy.orm import joinedload

from rapidly.core.extensions.sqlalchemy import sql
from rapidly.core.queries import Repository
from rapidly.core.utils import now_utc
from rapidly.models import EmailVerification


class EmailVerificationRepository(Repository[EmailVerification]):
    """Email verification queries: token lookup and expiry cleanup."""

    model = EmailVerification

    # ── Reads ──

    async def get_by_token_hash(self, token_hash: str) -> EmailVerification | None:
        stmt = (
            sql.select(EmailVerification)
            .where(
                EmailVerification.token_hash == token_hash,
                EmailVerification.expires_at > now_utc(),
            )
            .options(joinedload(EmailVerification.user))
        )
        return await self.get_one_or_none(stmt)

    # ── Writes ──

    async def delete_expired(self) -> None:
        stmt = delete(EmailVerification).where(EmailVerification.expires_at < now_utc())
        await self.session.execute(stmt)
        await self.session.flush()
