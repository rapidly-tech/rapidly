"""Database queries for member session lookup and lifecycle."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import contains_eager

from rapidly.core.queries import (
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
)
from rapidly.core.utils import now_utc
from rapidly.models import Member, MemberSession
from rapidly.models.customer import Customer


class MemberSessionRepository(
    SoftDeleteByIdMixin[MemberSession, UUID],
    SoftDeleteMixin[MemberSession],
    Repository[MemberSession],
):
    """Member-portal session persistence with token-hash lookups."""

    model = MemberSession

    async def get_by_token_hash(
        self, token_hash: str, *, expired: bool = False
    ) -> MemberSession | None:
        statement = (
            select(MemberSession)
            .join(MemberSession.member)
            .join(Member.customer)
            .where(
                MemberSession.token == token_hash,
                MemberSession.deleted_at.is_(None),
                Member.deleted_at.is_(None),
            )
            .options(
                contains_eager(MemberSession.member)
                .contains_eager(Member.customer)
                .joinedload(Customer.workspace)
            )
        )
        if not expired:
            statement = statement.where(MemberSession.expires_at > now_utc())

        result = await self.session.execute(statement)
        return result.unique().scalar_one_or_none()

    async def delete_expired(self) -> None:
        statement = delete(MemberSession).where(MemberSession.expires_at < now_utc())
        await self.session.execute(statement)
