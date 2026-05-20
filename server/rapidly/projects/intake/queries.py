"""Intake-work-item persistence layer."""

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
    IntakeWorkItem,
    Project,
    WorkItem,
    WorkspaceMembership,
)
from rapidly.projects.intake.ordering import IntakeWorkItemSortProperty


class IntakeWorkItemRepository(
    SoftDeleteMixin[IntakeWorkItem],
    FindByIdMixin[IntakeWorkItem, UUID],
    Repository[IntakeWorkItem],
):
    model = IntakeWorkItem

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[IntakeWorkItem]]:
        statement = (
            self.get_base_statement()
            .join(WorkItem, WorkItem.id == IntakeWorkItem.work_item_id)
            .join(Project, Project.id == WorkItem.project_id)
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
        statement: Select[tuple[IntakeWorkItem]],
        sorting: Sequence[Sorting[IntakeWorkItemSortProperty]],
    ) -> Select[tuple[IntakeWorkItem]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(IntakeWorkItem, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def get_by_work_item(self, work_item_id: UUID) -> IntakeWorkItem | None:
        statement = self.get_base_statement().where(
            IntakeWorkItem.work_item_id == work_item_id,
        )
        return await self.get_one_or_none(statement)
