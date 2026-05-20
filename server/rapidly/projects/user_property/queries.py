"""Project-user-property persistence layer."""

from uuid import UUID

from sqlalchemy import Select

from rapidly.core.queries import FindByIdMixin, Repository, SoftDeleteMixin
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import ProjectUserProperty


class ProjectUserPropertyRepository(
    SoftDeleteMixin[ProjectUserProperty],
    FindByIdMixin[ProjectUserProperty, UUID],
    Repository[ProjectUserProperty],
):
    model = ProjectUserProperty

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User]
    ) -> Select[tuple[ProjectUserProperty]]:
        """A user can only read their own property rows. No cross-user
        visibility — these are private prefs."""
        return self.get_base_statement().where(
            ProjectUserProperty.user_id == auth_subject.subject.id
        )

    async def get_for_user_and_project(
        self, user_id: UUID, project_id: UUID
    ) -> ProjectUserProperty | None:
        statement = self.get_base_statement().where(
            ProjectUserProperty.user_id == user_id,
            ProjectUserProperty.project_id == project_id,
        )
        return await self.get_one_or_none(statement)
