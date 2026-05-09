"""Workspace access token persistence layer.

``WorkspaceAccessTokenRepository`` handles token look-up by hash,
scope-filtered listing, usage-timestamp recording, and soft-delete.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, asc, desc, or_, select, update
from sqlalchemy.orm import contains_eager

from rapidly.core.queries import (
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
)
from rapidly.core.utils import now_utc
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import Workspace, WorkspaceAccessToken, WorkspaceMembership
from rapidly.platform.workspace_access_token.ordering import (
    WorkspaceAccessTokenSortProperty,
)
from rapidly.postgres import sql


class WorkspaceAccessTokenRepository(
    SoftDeleteByIdMixin[WorkspaceAccessToken, UUID],
    SoftDeleteMixin[WorkspaceAccessToken],
    Repository[WorkspaceAccessToken],
):
    """OAT persistence with hash-based token lookup and scope-aware queries."""

    model = WorkspaceAccessToken

    async def get_by_token_hash(
        self, token_hash: str, *, expired: bool = False
    ) -> WorkspaceAccessToken | None:
        statement = (
            self.get_base_statement()
            .join(WorkspaceAccessToken.workspace)
            .where(
                WorkspaceAccessToken.token == token_hash,
                Workspace.can_authenticate.is_(True),
            )
            .options(contains_eager(WorkspaceAccessToken.workspace))
        )
        if not expired:
            statement = statement.where(
                or_(
                    WorkspaceAccessToken.expires_at.is_(None),
                    WorkspaceAccessToken.expires_at > now_utc(),
                )
            )
        return await self.get_one_or_none(statement)

    async def record_usage(self, id: UUID, last_used_at: datetime) -> None:
        statement = (
            update(WorkspaceAccessToken)
            .where(WorkspaceAccessToken.id == id)
            .values(last_used_at=last_used_at)
        )
        await self.session.execute(statement)

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[WorkspaceAccessToken]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                WorkspaceAccessToken.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(
                WorkspaceAccessToken.workspace_id == auth_subject.subject.id
            )

        return statement

    def apply_list_filters(
        self,
        stmt: Select[tuple[WorkspaceAccessToken]],
        *,
        workspace_id: Sequence[UUID] | None = None,
        sorting: Sequence[tuple[WorkspaceAccessTokenSortProperty, bool]] = (),
    ) -> Select[tuple[WorkspaceAccessToken]]:
        if workspace_id is not None:
            stmt = stmt.where(WorkspaceAccessToken.workspace_id.in_(workspace_id))
        for criterion, is_desc in sorting:
            clause_fn = desc if is_desc else asc
            match criterion:
                case WorkspaceAccessTokenSortProperty.created_at:
                    stmt = stmt.order_by(clause_fn(WorkspaceAccessToken.created_at))
                case WorkspaceAccessTokenSortProperty.comment:
                    stmt = stmt.order_by(clause_fn(WorkspaceAccessToken.comment))
                case WorkspaceAccessTokenSortProperty.last_used_at:
                    stmt = stmt.order_by(clause_fn(WorkspaceAccessToken.last_used_at))
                case WorkspaceAccessTokenSortProperty.workspace_id:
                    stmt = stmt.order_by(clause_fn(WorkspaceAccessToken.workspace_id))
        return stmt

    async def count_by_workspace_id(
        self,
        workspace_id: UUID,
    ) -> int:
        """Count active workspace access tokens for an workspace."""
        count = await self.session.scalar(
            sql.select(sql.func.count(WorkspaceAccessToken.id)).where(
                WorkspaceAccessToken.workspace_id == workspace_id,
                WorkspaceAccessToken.deleted_at.is_(None),
            )
        )
        return count or 0
