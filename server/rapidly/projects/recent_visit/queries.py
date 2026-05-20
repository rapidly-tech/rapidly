"""Recent-visit persistence layer."""

from uuid import UUID

from sqlalchemy import Select

from rapidly.core.queries import FindByIdMixin, Repository, SoftDeleteMixin
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import RecentVisit, RecentVisitEntityType


class RecentVisitRepository(
    SoftDeleteMixin[RecentVisit],
    FindByIdMixin[RecentVisit, UUID],
    Repository[RecentVisit],
):
    model = RecentVisit

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User]
    ) -> Select[tuple[RecentVisit]]:
        return self.get_base_statement().where(
            RecentVisit.user_id == auth_subject.subject.id
        )

    async def get_for_triplet(
        self,
        user_id: UUID,
        entity_type: RecentVisitEntityType,
        entity_id: UUID,
    ) -> RecentVisit | None:
        statement = self.get_base_statement().where(
            RecentVisit.user_id == user_id,
            RecentVisit.entity_type == entity_type,
            RecentVisit.entity_id == entity_id,
        )
        return await self.get_one_or_none(statement)
