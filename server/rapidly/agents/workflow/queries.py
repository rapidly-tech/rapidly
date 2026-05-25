"""Workflow persistence layer."""

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
from rapidly.models import Workflow, WorkspaceMembership


class WorkflowRepository(
    SoftDeleteMixin[Workflow],
    FindByIdMixin[Workflow, UUID],
    Repository[Workflow],
):
    model = Workflow

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Workflow]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Workflow.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                Workflow.workspace_id == auth_subject.subject.id
            )

        return statement
