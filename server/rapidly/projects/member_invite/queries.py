"""Project-member-invite persistence layer."""

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
    ProjectMemberInvite,
    ProjectMemberInviteStatus,
    WorkspaceMembership,
)
from rapidly.projects.member_invite.ordering import ProjectMemberInviteSortProperty


class ProjectMemberInviteRepository(
    SoftDeleteMixin[ProjectMemberInvite],
    FindByIdMixin[ProjectMemberInvite, UUID],
    Repository[ProjectMemberInvite],
):
    model = ProjectMemberInvite

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[ProjectMemberInvite]]:
        """An invite is readable if the caller is:
        - the invitee (so they can see their pending invites), OR
        - any member of the project's workspace (so admins can list /
          review). Role-gating to admin-only happens in the action
          layer; the read filter only narrows by workspace boundary.
        """
        statement = self.get_base_statement().join(
            Project, Project.id == ProjectMemberInvite.project_id
        )

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                (ProjectMemberInvite.invitee_id == user.id)
                | (
                    Project.workspace_id.in_(
                        select(WorkspaceMembership.workspace_id).where(
                            WorkspaceMembership.user_id == user.id,
                            WorkspaceMembership.deleted_at.is_(None),
                        )
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(Project.workspace_id == auth_subject.subject.id)

        return statement

    def apply_sorting(
        self,
        statement: Select[tuple[ProjectMemberInvite]],
        sorting: Sequence[Sorting[ProjectMemberInviteSortProperty]],
    ) -> Select[tuple[ProjectMemberInvite]]:
        clauses: list[UnaryExpression[Any]] = []
        for criterion, is_desc in sorting:
            fn = desc if is_desc else asc
            column = getattr(ProjectMemberInvite, criterion.value)
            clauses.append(fn(column))
        return statement.order_by(*clauses) if clauses else statement

    async def get_pending_for_user_and_project(
        self, project_id: UUID, invitee_id: UUID
    ) -> ProjectMemberInvite | None:
        statement = self.get_base_statement().where(
            ProjectMemberInvite.project_id == project_id,
            ProjectMemberInvite.invitee_id == invitee_id,
            ProjectMemberInvite.status == ProjectMemberInviteStatus.pending,
        )
        return await self.get_one_or_none(statement)

    async def get_by_token(self, token: str) -> ProjectMemberInvite | None:
        statement = self.get_base_statement().where(
            ProjectMemberInvite.token == token,
        )
        return await self.get_one_or_none(statement)
