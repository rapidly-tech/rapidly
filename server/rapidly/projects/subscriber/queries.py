"""Work-item subscriber persistence layer."""

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
    WorkItem,
    WorkItemSubscriber,
    WorkspaceMembership,
)
from rapidly.projects.subscriber.ordering import WorkItemSubscriberSortProperty


class WorkItemSubscriberRepository(
    SoftDeleteMixin[WorkItemSubscriber],
    FindByIdMixin[WorkItemSubscriber, UUID],
    Repository[WorkItemSubscriber],
):
    model = WorkItemSubscriber

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkItemSubscriber]]:
        statement = (
            self.get_base_statement()
            .join(WorkItem, WorkItem.id == WorkItemSubscriber.work_item_id)
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
        statement: Select[tuple[WorkItemSubscriber]],
        sorting: Sequence[Sorting[WorkItemSubscriberSortProperty]],
    ) -> Select[tuple[WorkItemSubscriber]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(WorkItemSubscriber, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def get_for_user_and_work_item(
        self, user_id: UUID, work_item_id: UUID
    ) -> WorkItemSubscriber | None:
        statement = self.get_base_statement().where(
            WorkItemSubscriber.user_id == user_id,
            WorkItemSubscriber.work_item_id == work_item_id,
        )
        return await self.get_one_or_none(statement)
