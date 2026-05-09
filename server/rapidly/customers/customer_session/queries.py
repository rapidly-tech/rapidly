"""Customer session persistence layer.

``CustomerSessionRepository`` handles token-hash lookups and
expired-session cleanup for the customer portal authentication flow.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm.strategy_options import contains_eager

from rapidly.core.queries import Repository
from rapidly.core.utils import now_utc
from rapidly.models import Customer, CustomerSession


class CustomerSessionRepository(Repository[CustomerSession]):
    """Customer session queries: token lookup and expiry cleanup."""

    model = CustomerSession

    # ── Reads ──

    async def get_by_token_hash(
        self, token_hash: str, *, expired: bool = False
    ) -> CustomerSession | None:
        """Look up a session by its hashed token, joining the customer and workspace."""
        statement = (
            select(CustomerSession)
            .join(CustomerSession.customer)
            .where(
                CustomerSession.token == token_hash,
                CustomerSession.deleted_at.is_(None),
                Customer.can_authenticate.is_(True),
            )
            .options(
                contains_eager(CustomerSession.customer).joinedload(Customer.workspace)
            )
        )
        if not expired:
            statement = statement.where(CustomerSession.expires_at > now_utc())

        return await self.get_one_or_none(statement)

    # ── Writes ──

    async def delete_expired(self) -> None:
        """Remove all sessions whose expiry has passed."""
        statement = delete(CustomerSession).where(
            CustomerSession.expires_at < now_utc()
        )
        await self.session.execute(statement)
