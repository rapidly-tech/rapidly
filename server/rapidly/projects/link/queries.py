"""Work-item relation persistence layer."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, asc, desc, or_, select
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
    WorkItem,
    WorkItemRelation,
    WorkspaceMembership,
)
from rapidly.projects.link.ordering import WorkItemRelationSortProperty


class WorkItemRelationRepository(
    SoftDeleteMixin[WorkItemRelation],
    FindByIdMixin[WorkItemRelation, UUID],
    Repository[WorkItemRelation],
):
    model = WorkItemRelation

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkItemRelation]]:
        statement = (
            self.get_base_statement()
            .join(WorkItem, WorkItem.id == WorkItemRelation.work_item_id)
            .join(Project, Project.id == WorkItem.project_id)
            # Soft-deleted parents (work item or project) must never
            # surface their relations to readers.
            .where(
                WorkItem.deleted_at.is_(None),
                Project.deleted_at.is_(None),
            )
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
        statement: Select[tuple[WorkItemRelation]],
        sorting: Sequence[Sorting[WorkItemRelationSortProperty]],
    ) -> Select[tuple[WorkItemRelation]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(WorkItemRelation, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def get_for_work_item(self, work_item_id: UUID) -> Sequence[WorkItemRelation]:
        """Return both directions — relations originating from this item
        and those that reference it as the target — so callers can render
        the full edge set."""
        statement = self.get_base_statement().where(
            or_(
                WorkItemRelation.work_item_id == work_item_id,
                WorkItemRelation.related_id == work_item_id,
            )
        )
        return await self.get_all(statement)
