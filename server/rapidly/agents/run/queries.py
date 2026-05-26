"""Run persistence layer.

Immutable from the API's perspective — the engine (M4.2) is the
only writer for status / output_data / error_message. The repo
omits ``soft_delete`` and ``update`` paths from the public
surface; internal helpers reach in for the engine's state writes
in M4.2.
"""

from uuid import UUID

from sqlalchemy import Select, select

from rapidly.core.queries import FindByIdMixin, Repository
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Run, Workflow, WorkflowVersion, WorkspaceMembership


class RunRepository(
    FindByIdMixin[Run, UUID],
    Repository[Run],
):
    model = Run

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Run]]:
        # Two-hop join: Run -> WorkflowVersion -> Workflow ->
        # workspace membership. The hop through WorkflowVersion is
        # what binds a run to a workspace at the SQL level (Run
        # itself has no workspace_id column; the WorkflowVersion
        # snapshot lives on the workflow, which is workspace-scoped).
        statement = (
            self.get_base_statement()
            .join(WorkflowVersion, WorkflowVersion.id == Run.workflow_version_id)
            .join(Workflow, Workflow.id == WorkflowVersion.workflow_id)
        )

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
