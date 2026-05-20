"""Module-member + module-link persistence layer.

Both repositories share the same workspace-bounded readability
filter: join through ProjectModule → Project → WorkspaceMembership.
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, asc, desc, select
from sqlalchemy.sql.elements import UnaryExpression

from rapidly.core.ordering import Sorting
from rapidly.core.queries import FindByIdMixin, Repository, SoftDeleteMixin
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import (
    Project,
    ProjectModule,
    ProjectModuleLink,
    ProjectModuleMember,
    WorkspaceMembership,
)
from rapidly.projects.module_extras.ordering import ModuleExtrasSortProperty


def _workspace_filter(
    statement: Select[Any], auth_subject: AuthPrincipal[User | Workspace]
) -> Select[Any]:
    if is_user_principal(auth_subject):
        user = auth_subject.subject
        return statement.where(
            Project.workspace_id.in_(
                select(WorkspaceMembership.workspace_id).where(
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.deleted_at.is_(None),
                )
            )
        )
    if is_workspace_principal(auth_subject):
        return statement.where(Project.workspace_id == auth_subject.subject.id)
    return statement


def _sort(
    statement: Select[Any],
    model: Any,
    sorting: Sequence[Sorting[ModuleExtrasSortProperty]],
) -> Select[Any]:
    clauses: list[UnaryExpression[Any]] = []
    for criterion, is_desc in sorting:
        fn = desc if is_desc else asc
        column = getattr(model, criterion.value)
        clauses.append(fn(column))
    return statement.order_by(*clauses) if clauses else statement


class ProjectModuleMemberRepository(
    SoftDeleteMixin[ProjectModuleMember],
    FindByIdMixin[ProjectModuleMember, UUID],
    Repository[ProjectModuleMember],
):
    model = ProjectModuleMember

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[ProjectModuleMember]]:
        statement = (
            self.get_base_statement()
            .join(ProjectModule, ProjectModule.id == ProjectModuleMember.module_id)
            .join(Project, Project.id == ProjectModule.project_id)
        )
        return _workspace_filter(statement, auth_subject)

    def apply_sorting(
        self,
        statement: Select[tuple[ProjectModuleMember]],
        sorting: Sequence[Sorting[ModuleExtrasSortProperty]],
    ) -> Select[tuple[ProjectModuleMember]]:
        return _sort(statement, ProjectModuleMember, sorting)

    async def get_for_module_and_user(
        self, module_id: UUID, user_id: UUID
    ) -> ProjectModuleMember | None:
        statement = self.get_base_statement().where(
            ProjectModuleMember.module_id == module_id,
            ProjectModuleMember.user_id == user_id,
        )
        return await self.get_one_or_none(statement)


class ProjectModuleLinkRepository(
    SoftDeleteMixin[ProjectModuleLink],
    FindByIdMixin[ProjectModuleLink, UUID],
    Repository[ProjectModuleLink],
):
    model = ProjectModuleLink

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[ProjectModuleLink]]:
        statement = (
            self.get_base_statement()
            .join(ProjectModule, ProjectModule.id == ProjectModuleLink.module_id)
            .join(Project, Project.id == ProjectModule.project_id)
        )
        return _workspace_filter(statement, auth_subject)

    def apply_sorting(
        self,
        statement: Select[tuple[ProjectModuleLink]],
        sorting: Sequence[Sorting[ModuleExtrasSortProperty]],
    ) -> Select[tuple[ProjectModuleLink]]:
        return _sort(statement, ProjectModuleLink, sorting)
