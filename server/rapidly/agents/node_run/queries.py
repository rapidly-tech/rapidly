"""NodeRun persistence layer.

Read-only surface from the API. The engine (M4.2) writes via this
repo's ``create`` + ``update`` (inherited from the Repository
base) — those aren't exposed through any HTTP endpoint.
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
from rapidly.models import (
    NodeRun,
    Run,
    Workflow,
    WorkflowVersion,
    WorkspaceMembership,
)


class NodeRunRepository(
    FindByIdMixin[NodeRun, UUID],
    Repository[NodeRun],
):
    model = NodeRun

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[NodeRun]]:
        # Three-hop join: NodeRun -> Run -> WorkflowVersion ->
        # Workflow -> workspace membership. The chain mirrors the
        # one in RunRepository (M4.1c) extended by one hop.
        statement = (
            self.get_base_statement()
            .join(Run, Run.id == NodeRun.run_id)
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
