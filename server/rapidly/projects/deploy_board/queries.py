"""Project deploy-board persistence layer."""

from uuid import UUID

from sqlalchemy import Select, select

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
    ProjectDeployBoard,
    WorkspaceMembership,
)


class ProjectDeployBoardRepository(
    SoftDeleteMixin[ProjectDeployBoard],
    FindByIdMixin[ProjectDeployBoard, UUID],
    Repository[ProjectDeployBoard],
):
    model = ProjectDeployBoard

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[ProjectDeployBoard]]:
        statement = self.get_base_statement().join(
            Project, Project.id == ProjectDeployBoard.project_id
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

    async def get_by_project(self, project_id: UUID) -> ProjectDeployBoard | None:
        statement = self.get_base_statement().where(
            ProjectDeployBoard.project_id == project_id,
        )
        return await self.get_one_or_none(statement)

    async def get_by_token(self, token: str) -> ProjectDeployBoard | None:
        statement = self.get_base_statement().where(
            ProjectDeployBoard.token == token,
        )
        return await self.get_one_or_none(statement)
