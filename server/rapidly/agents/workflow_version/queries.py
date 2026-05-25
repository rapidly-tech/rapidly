"""WorkflowVersion persistence layer.

Append-only: the repository deliberately omits ``soft_delete`` /
``update`` paths. Snapshots are forever (cascade-deleted with their
parent Workflow).
"""

from uuid import UUID

from sqlalchemy import Select, func, select

from rapidly.core.queries import FindByIdMixin, Repository
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Workflow, WorkflowVersion, WorkspaceMembership


class WorkflowVersionRepository(
    FindByIdMixin[WorkflowVersion, UUID],
    Repository[WorkflowVersion],
):
    model = WorkflowVersion

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkflowVersion]]:
        statement = self.get_base_statement().join(
            Workflow, Workflow.id == WorkflowVersion.workflow_id
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

    async def next_version_number(self, workflow_id: UUID) -> int:
        """Return ``MAX(version_number) + 1`` for ``workflow_id``.

        Concurrent ``create_version`` calls race here; the unique
        constraint on (workflow_id, version_number) is the
        authoritative serializer. Callers should catch
        ``IntegrityError`` and retry. For v1 this is acceptable —
        the editor only publishes one version at a time per user
        session.
        """
        stmt = select(func.coalesce(func.max(WorkflowVersion.version_number), 0)).where(
            WorkflowVersion.workflow_id == workflow_id
        )
        result = await self.session.execute(stmt)
        max_version = result.scalar_one()
        return int(max_version) + 1
