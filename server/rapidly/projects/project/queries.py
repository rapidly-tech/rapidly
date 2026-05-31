"""Project persistence layer with workspace scoping and slug/identifier look-ups."""

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
from rapidly.models import Project, WorkspaceMembership
from rapidly.projects.project.ordering import ProjectSortProperty


class ProjectRepository(
    SoftDeleteMixin[Project],
    FindByIdMixin[Project, UUID],
    Repository[Project],
):
    """Workspace-scoped project queries."""

    model = Project

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Project]]:
        statement = self.get_base_statement()

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
        statement: Select[tuple[Project]],
        sorting: Sequence[Sorting[ProjectSortProperty]],
    ) -> Select[tuple[Project]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(Project, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def get_by_slug(self, workspace_id: UUID, slug: str) -> Project | None:
        statement = self.get_base_statement().where(
            Project.workspace_id == workspace_id,
            Project.slug == slug,
        )
        return await self.get_one_or_none(statement)

    async def get_by_identifier(
        self, workspace_id: UUID, identifier: str
    ) -> Project | None:
        statement = self.get_base_statement().where(
            Project.workspace_id == workspace_id,
            Project.identifier == identifier,
        )
        return await self.get_one_or_none(statement)
