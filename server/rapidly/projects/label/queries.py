"""Project label persistence layer."""

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
from rapidly.models import Project, ProjectLabel, WorkspaceMembership
from rapidly.projects.label.ordering import ProjectLabelSortProperty


class ProjectLabelRepository(
    SoftDeleteMixin[ProjectLabel],
    FindByIdMixin[ProjectLabel, UUID],
    Repository[ProjectLabel],
):
    model = ProjectLabel

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[ProjectLabel]]:
        statement = self.get_base_statement().join(
            Project, Project.id == ProjectLabel.project_id
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
        statement: Select[tuple[ProjectLabel]],
        sorting: Sequence[Sorting[ProjectLabelSortProperty]],
    ) -> Select[tuple[ProjectLabel]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(ProjectLabel, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def get_by_name(self, project_id: UUID, name: str) -> ProjectLabel | None:
        statement = self.get_base_statement().where(
            ProjectLabel.project_id == project_id,
            ProjectLabel.name == name,
        )
        return await self.get_one_or_none(statement)
