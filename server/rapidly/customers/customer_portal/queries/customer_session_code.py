"""Database queries for customer session code lookup and validation.

Session codes are short-lived tokens that grant portal access.
Only non-expired rows are returned by the query helpers below.
"""

from sqlalchemy import Select, select
from sqlalchemy.orm import joinedload

from rapidly.core.queries import Repository
from rapidly.core.utils import now_utc
from rapidly.models import Customer, CustomerSessionCode


def _valid_code_base_query(code_hash: str) -> Select[tuple[CustomerSessionCode]]:
    """Build a SELECT for a non-expired session code with eager-loaded relations."""
    return (
        select(CustomerSessionCode)
        .where(
            CustomerSessionCode.expires_at > now_utc(),
            CustomerSessionCode.code == code_hash,
        )
        .options(
            joinedload(CustomerSessionCode.customer).joinedload(Customer.workspace)
        )
    )


class CustomerSessionCodeRepository(Repository[CustomerSessionCode]):
    model = CustomerSessionCode

    def get_valid_by_code_hash_statement(
        self, code_hash: str
    ) -> Select[tuple[CustomerSessionCode]]:
        """Return a statement selecting a valid (non-expired) code by its hash."""
        return _valid_code_base_query(code_hash)

    async def get_valid_by_code_hash(
        self, code_hash: str
    ) -> CustomerSessionCode | None:
        """Execute the lookup and return the row, or ``None`` if expired/missing."""
        stmt = self.get_valid_by_code_hash_statement(code_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
