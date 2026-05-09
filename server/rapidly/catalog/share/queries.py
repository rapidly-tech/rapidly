"""Share persistence layer with price-aware queries and full-text search.

``ShareRepository`` handles visibility-scoped listing, eager-loading
of prices / media / custom fields, billing-type inference, and
full-text search against the ``search_vector`` GIN index.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import joinedload, selectinload

from rapidly.core.metadata import MetadataQuery, apply_metadata_clause
from rapidly.core.queries import (
    Options,
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
    SortableMixin,
    SortingClause,
)
from rapidly.core.queries.utils import escape_like
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import (
    Share,
    SharePrice,
    SharePriceCustom,
    SharePriceFixed,
    ShareVisibility,
    WorkspaceMembership,
)
from rapidly.models.share_price import SharePriceAmountType
from rapidly.postgres import sql

from .ordering import ShareSortProperty


class ShareRepository(
    SortableMixin[Share, ShareSortProperty],
    SoftDeleteByIdMixin[Share, UUID],
    SoftDeleteMixin[Share],
    Repository[Share],
):
    """Share queries with workspace scoping and price-aware listing."""

    model = Share

    # ── Reads ──

    async def get_by_id_and_workspace(
        self,
        id: UUID,
        workspace_id: UUID,
        *,
        options: Options = (),
    ) -> Share | None:
        statement = (
            self.get_base_statement()
            .where(Share.id == id, Share.workspace_id == workspace_id)
            .options(*options)
        )
        return await self.get_one_or_none(statement)

    def get_eager_options(self) -> Options:
        return (
            joinedload(Share.workspace),
            selectinload(Share.share_medias),
            selectinload(Share.attached_custom_fields),
            selectinload(Share.all_prices),
        )

    def get_readable_statement(
        self, auth_subject: AuthPrincipal[User | Workspace]
    ) -> Select[tuple[Share]]:
        statement = self.get_base_statement()

        if is_user_principal(auth_subject):
            user = auth_subject.subject
            statement = statement.where(
                Share.workspace_id.in_(
                    select(WorkspaceMembership.workspace_id).where(
                        WorkspaceMembership.user_id == user.id,
                        WorkspaceMembership.deleted_at.is_(None),
                    )
                )
            )
        elif is_workspace_principal(auth_subject):
            statement = statement.where(Share.workspace_id == auth_subject.subject.id)

        return statement

    def get_list_statement(
        self,
        auth_subject: AuthPrincipal[User | Workspace],
    ) -> Select[tuple[Share]]:
        """Get a list-ready statement with the SharePrice join."""
        return self.get_readable_statement(auth_subject).join(
            SharePrice,
            onclause=(
                SharePrice.id
                == select(SharePrice)
                .correlate(Share)
                .with_only_columns(SharePrice.id)
                .where(
                    SharePrice.share_id == Share.id,
                    SharePrice.is_archived.is_(False),
                    SharePrice.deleted_at.is_(None),
                )
                .order_by(SharePrice.created_at.asc())
                .limit(1)
                .scalar_subquery()
            ),
            isouter=True,
        )

    def apply_list_filters(
        self,
        stmt: Select[tuple[Share]],
        *,
        id: Sequence[UUID] | None = None,
        workspace_id: Sequence[UUID] | None = None,
        query: str | None = None,
        is_archived: bool | None = None,
        visibility: Sequence[ShareVisibility] | None = None,
        metadata: MetadataQuery | None = None,
    ) -> Select[tuple[Share]]:
        if id is not None:
            stmt = stmt.where(Share.id.in_(id))
        if workspace_id is not None:
            stmt = stmt.where(Share.workspace_id.in_(workspace_id))
        if query is not None:
            stmt = stmt.where(Share.name.ilike(f"%{escape_like(query)}%"))
        if is_archived is not None:
            stmt = stmt.where(Share.is_archived.is_(is_archived))
        if visibility is not None:
            stmt = stmt.where(Share.visibility.in_(visibility))
        if metadata is not None:
            stmt = apply_metadata_clause(Share, stmt, metadata)
        return stmt

    async def count_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        is_archived: bool | None = None,
    ) -> int:
        """Count products for an workspace with optional archived filter."""
        statement = sql.select(sql.func.count(Share.id)).where(
            Share.workspace_id == workspace_id,
            Share.deleted_at.is_(None),
        )

        if is_archived is not None:
            statement = statement.where(Share.is_archived.is_(is_archived))

        count = await self.session.scalar(statement)
        return count or 0

    def get_sorting_clause(self, property: ShareSortProperty) -> SortingClause:
        match property:
            case ShareSortProperty.created_at:
                return Share.created_at
            case ShareSortProperty.product_name:
                return Share.name
            case ShareSortProperty.price_amount_type:
                return case(
                    (
                        SharePrice.amount_type == SharePriceAmountType.free,
                        1,
                    ),
                    (
                        SharePrice.amount_type == SharePriceAmountType.custom,
                        2,
                    ),
                    (
                        SharePrice.amount_type == SharePriceAmountType.fixed,
                        3,
                    ),
                )
            case ShareSortProperty.price_amount:
                return case(
                    (
                        SharePrice.amount_type == SharePriceAmountType.free,
                        -2,
                    ),
                    (
                        SharePrice.amount_type == SharePriceAmountType.custom,
                        func.coalesce(SharePriceCustom.minimum_amount, -1),
                    ),
                    (
                        SharePrice.amount_type == SharePriceAmountType.fixed,
                        SharePriceFixed.price_amount,
                    ),
                )
