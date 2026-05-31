"""Cycle persistence layer."""

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
    ProjectCycle,
    ProjectCycleWorkItem,
    WorkspaceMembership,
)
from rapidly.projects.cycle.ordering import ProjectCycleSortProperty


class ProjectCycleRepository(
    SoftDeleteMixin[ProjectCycle],
    FindByIdMixin[ProjectCycle, UUID],
    Repository[ProjectCycle],
):
    model = ProjectCycle

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[ProjectCycle]]:
        statement = self.get_base_statement().join(
            Project, Project.id == ProjectCycle.project_id
        )

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Project.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(Project.workspace_id == auth_subject.subject.id)

        return statement

    def apply_sorting(
        self,
        statement: Select[tuple[ProjectCycle]],
        sorting: Sequence[Sorting[ProjectCycleSortProperty]],
    ) -> Select[tuple[ProjectCycle]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(ProjectCycle, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def get_by_name(self, project_id: UUID, name: str) -> ProjectCycle | None:
        statement = self.get_base_statement().where(
            ProjectCycle.project_id == project_id,
            ProjectCycle.name == name,
        )
        return await self.get_one_or_none(statement)


class ProjectCycleWorkItemRepository(
    SoftDeleteMixin[ProjectCycleWorkItem],
    FindByIdMixin[ProjectCycleWorkItem, UUID],
    Repository[ProjectCycleWorkItem],
):
    model = ProjectCycleWorkItem

    async def existing_for_cycle(
        self, cycle_id: UUID
    ) -> dict[UUID, ProjectCycleWorkItem]:
        statement = self.get_base_statement().where(
            ProjectCycleWorkItem.cycle_id == cycle_id
        )
        rows = await self.get_all(statement)
        return {row.work_item_id: row for row in rows}
