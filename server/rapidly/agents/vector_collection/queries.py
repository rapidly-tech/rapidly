"""VectorCollection persistence layer.

Tenancy: a User principal sees only collections in workspaces they
have a (non-deleted) membership in; a Workspace principal sees only
its own. Matches the Workflow repo's shape.
"""

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
from rapidly.models import VectorCollection, WorkspaceMembership


class VectorCollectionRepository(
    SoftDeleteMixin[VectorCollection],
    FindByIdMixin[VectorCollection, UUID],
    Repository[VectorCollection],
):
    model = VectorCollection

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[VectorCollection]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                VectorCollection.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                VectorCollection.workspace_id == auth_subject.subject.id
            )

        return statement
