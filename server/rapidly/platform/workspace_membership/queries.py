"""Workspace membership persistence layer.

``WorkspaceMembershipRepository`` handles reads and writes for the
user-to-workspace join records, including eager-loading of related
user and workspace associations.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import joinedload

from rapidly.core.queries import Repository, SoftDeleteMixin
from rapidly.core.utils import now_utc
from rapidly.models import WorkspaceMembership


class WorkspaceMembershipRepository(
    SoftDeleteMixin[WorkspaceMembership],
    Repository[WorkspaceMembership],
):
    """Workspace membership queries with eager-loaded relationships."""

    model = WorkspaceMembership

    # ── Reads ──

    async def list_by_workspace(
        self,
        workspace_id: UUID,
    ) -> Sequence[WorkspaceMembership]:
        stmt = (
            self.get_base_statement()
            .where(WorkspaceMembership.workspace_id == workspace_id)
            .options(
                joinedload(WorkspaceMembership.user),
                joinedload(WorkspaceMembership.workspace),
            )
        )
        return await self.get_all(stmt)

    async def get_member_count(
        self,
        workspace_id: UUID,
    ) -> int:
        """Get the count of active members in a workspace."""
        stmt = select(func.count(WorkspaceMembership.user_id)).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        count = result.scalar()
        return count if count else 0

    async def list_by_user_id(
        self,
        user_id: UUID,
    ) -> Sequence[WorkspaceMembership]:
        stmt = self._get_list_by_user_id_query(user_id)
        return await self.get_all(stmt)

    async def get_workspace_membership_count(
        self,
        user_id: UUID,
    ) -> int:
        stmt = self._get_list_by_user_id_query(
            user_id, ordered=False
        ).with_only_columns(func.count(WorkspaceMembership.workspace_id))
        result = await self.session.execute(stmt)
        count = result.scalar()
        return count if count else 0

    async def get_by_user_and_org(
        self,
        user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMembership | None:
        stmt = (
            self.get_base_statement()
            .where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
            .options(
                joinedload(WorkspaceMembership.user),
                joinedload(WorkspaceMembership.workspace),
            )
        )
        return await self.get_one_or_none(stmt)

    # ── Writes ──

    async def remove_member(
        self,
        user_id: UUID,
        workspace_id: UUID,
    ) -> None:
        """Soft-delete a membership by setting deleted_at."""
        stmt = (
            update(WorkspaceMembership)
            .where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.deleted_at.is_(None),
            )
            .values(deleted_at=now_utc())
        )
        await self.session.execute(stmt)

    # ── Private helpers ──

    @staticmethod
    def _get_list_by_user_id_query(
        user_id: UUID, ordered: bool = True
    ) -> Select[tuple[WorkspaceMembership]]:
        stmt = (
            select(WorkspaceMembership)
            .where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.deleted_at.is_(None),
            )
            .options(
                joinedload(WorkspaceMembership.user),
                joinedload(WorkspaceMembership.workspace),
            )
        )
        if ordered:
            stmt = stmt.order_by(WorkspaceMembership.created_at.asc())

        return stmt
