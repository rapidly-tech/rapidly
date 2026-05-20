"""Cycle/module user-property persistence layer.

Read filter is hard-coded to the calling user across both repos —
these are private prefs; no cross-user visibility.
"""

from uuid import UUID

from sqlalchemy import Select

from rapidly.core.queries import FindByIdMixin, Repository, SoftDeleteMixin
from rapidly.identity.auth.models import AuthPrincipal, User
from rapidly.models import ProjectCycleUserProperty, ProjectModuleUserProperty


class ProjectCycleUserPropertyRepository(
    SoftDeleteMixin[ProjectCycleUserProperty],
    FindByIdMixin[ProjectCycleUserProperty, UUID],
    Repository[ProjectCycleUserProperty],
):
    model = ProjectCycleUserProperty

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User]
    ) -> Select[tuple[ProjectCycleUserProperty]]:
        return self.get_base_statement().where(
            ProjectCycleUserProperty.user_id == auth_subject.subject.id
        )

    async def get_for_user_and_cycle(
        self, user_id: UUID, cycle_id: UUID
    ) -> ProjectCycleUserProperty | None:
        statement = self.get_base_statement().where(
            ProjectCycleUserProperty.user_id == user_id,
            ProjectCycleUserProperty.cycle_id == cycle_id,
        )
        return await self.get_one_or_none(statement)


class ProjectModuleUserPropertyRepository(
    SoftDeleteMixin[ProjectModuleUserProperty],
    FindByIdMixin[ProjectModuleUserProperty, UUID],
    Repository[ProjectModuleUserProperty],
):
    model = ProjectModuleUserProperty

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User]
    ) -> Select[tuple[ProjectModuleUserProperty]]:
        return self.get_base_statement().where(
            ProjectModuleUserProperty.user_id == auth_subject.subject.id
        )

    async def get_for_user_and_module(
        self, user_id: UUID, module_id: UUID
    ) -> ProjectModuleUserProperty | None:
        statement = self.get_base_statement().where(
            ProjectModuleUserProperty.user_id == user_id,
            ProjectModuleUserProperty.module_id == module_id,
        )
        return await self.get_one_or_none(statement)
