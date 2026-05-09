"""Storefront persistence layer.

Read-only queries for the public-facing storefront, returning
visible workspaces, products, and file shares filtered by slug.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.queries import Repository
from rapidly.models import Customer, Workspace
from rapidly.models.file_share_session import FileShareSession, FileShareSessionStatus


class StorefrontRepository(Repository[Workspace]):
    """Read-only storefront queries for public workspace profiles."""

    model = Workspace

    # ── Workspace lookups ──

    async def get_by_slug(self, slug: str) -> Workspace | None:
        """Find a publicly visible workspace by its slug."""
        statement = select(Workspace).where(
            Workspace.deleted_at.is_(None),
            Workspace.blocked_at.is_(None),
            Workspace.slug == slug,
            Workspace.storefront_enabled.is_(True),
        )
        return await self.get_one_or_none(statement)

    # ── File share lookups ──

    async def list_public_file_shares(
        self, workspace_id: UUID
    ) -> Sequence[FileShareSession]:
        """List active paid file shares for a workspace's public page."""
        statement = (
            select(FileShareSession)
            .where(
                FileShareSession.workspace_id == workspace_id,
                FileShareSession.deleted_at.is_(None),
                FileShareSession.status == FileShareSessionStatus.active,
                FileShareSession.price_cents.isnot(None),
                FileShareSession.price_cents > 0,
            )
            .order_by(FileShareSession.created_at.desc())
            .limit(100)
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    # ── Customer lookups ──

    async def list_customers(
        self,
        workspace: Workspace,
        *,
        pagination: PaginationParams,
    ) -> tuple[Sequence[Customer], int]:
        statement = select(Customer).where(
            Customer.workspace_id == workspace.id,
            Customer.deleted_at.is_(None),
        )
        results, count = await paginate(self.session, statement, pagination=pagination)
        return results, count
