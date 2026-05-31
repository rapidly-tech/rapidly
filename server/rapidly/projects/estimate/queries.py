"""Persistence layer for estimate scales and their points."""

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
    ProjectEstimate,
    ProjectEstimatePoint,
    WorkspaceMembership,
)
from rapidly.projects.estimate.ordering import ProjectEstimateSortProperty


class ProjectEstimateRepository(
    SoftDeleteMixin[ProjectEstimate],
    FindByIdMixin[ProjectEstimate, UUID],
    Repository[ProjectEstimate],
):
    model = ProjectEstimate

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[ProjectEstimate]]:
        statement = self.get_base_statement().join(
            Project, Project.id == ProjectEstimate.project_id
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
        statement: Select[tuple[ProjectEstimate]],
        sorting: Sequence[Sorting[ProjectEstimateSortProperty]],
    ) -> Select[tuple[ProjectEstimate]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(ProjectEstimate, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def get_by_name(self, project_id: UUID, name: str) -> ProjectEstimate | None:
        statement = self.get_base_statement().where(
            ProjectEstimate.project_id == project_id,
            ProjectEstimate.name == name,
        )
        return await self.get_one_or_none(statement)


class ProjectEstimatePointRepository(
    SoftDeleteMixin[ProjectEstimatePoint],
    FindByIdMixin[ProjectEstimatePoint, UUID],
    Repository[ProjectEstimatePoint],
):
    model = ProjectEstimatePoint

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[ProjectEstimatePoint]]:
        statement = (
            self.get_base_statement()
            .join(
                ProjectEstimate, ProjectEstimate.id == ProjectEstimatePoint.estimate_id
            )
            .join(Project, Project.id == ProjectEstimate.project_id)
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

    async def get_by_estimate_and_key(
        self, estimate_id: UUID, key: int
    ) -> ProjectEstimatePoint | None:
        statement = self.get_base_statement().where(
            ProjectEstimatePoint.estimate_id == estimate_id,
            ProjectEstimatePoint.key == key,
        )
        return await self.get_one_or_none(statement)
