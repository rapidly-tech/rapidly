"""Activity persistence layer.

Activities are read-only by callers but write-able internally — only
this module's ``emit`` helper adds rows.  The repository inherits the
soft-delete mixin so retention sweeps can purge old rows without
breaking foreign keys.
"""

from collections.abc import Sequence
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
    WorkItem,
    WorkItemActivity,
    WorkspaceMembership,
)


class WorkItemActivityRepository(
    SoftDeleteMixin[WorkItemActivity],
    FindByIdMixin[WorkItemActivity, UUID],
    Repository[WorkItemActivity],
):
    model = WorkItemActivity

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkItemActivity]]:
        statement = (
            self.get_base_statement()
            .join(WorkItem, WorkItem.id == WorkItemActivity.work_item_id)
            .join(Project, Project.id == WorkItem.project_id)
            # Soft-deleted parents (work item or project) must never
            # surface their activity log to readers.
            .where(
                WorkItem.deleted_at.is_(None),
                Project.deleted_at.is_(None),
            )
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

    async def get_for_work_item(
        self, auth_subject: AuthPrincipal[User | Workspace], work_item_id: UUID
    ) -> Sequence[WorkItemActivity]:
        statement = (
            self.get_readable_statement(auth_subject)
            .where(WorkItemActivity.work_item_id == work_item_id)
            .order_by(WorkItemActivity.created_at.desc())
        )
        return await self.get_all(statement)
