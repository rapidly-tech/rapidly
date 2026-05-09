"""Customer-portal workspace service: public profile and share queries."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from rapidly.models import Share, ShareVisibility, Workspace
from rapidly.postgres import AsyncSession


class CustomerWorkspaceService:
    async def get_by_slug(self, session: AsyncSession, slug: str) -> Workspace | None:
        statement = (
            select(Workspace)
            .where(
                Workspace.deleted_at.is_(None),
                Workspace.blocked_at.is_(None),
                Workspace.slug == slug,
            )
            .options(
                selectinload(
                    Workspace.shares.and_(
                        Share.deleted_at.is_(None),
                        Share.is_archived.is_(False),
                        Share.visibility == ShareVisibility.public,
                    )
                ).options(
                    selectinload(Share.share_medias),
                )
            )
        )
        result = await session.execute(statement)
        return result.unique().scalar_one_or_none()


customer_workspace = CustomerWorkspaceService()
