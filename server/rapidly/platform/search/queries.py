"""Cross-entity search persistence layer.

``SearchRepository`` executes unified full-text queries across products,
customers, and workspaces using PostgreSQL ``ts_vector`` GIN indexes with
rank-based ordering.
"""

import uuid
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Select,
    String,
    func,
    literal,
    or_,
    select,
    union_all,
)

from rapidly.core.db.postgres import AsyncReadSession
from rapidly.models import (
    Customer,
    Share,
    Workspace,
    WorkspaceMembership,
)


class SearchRepository:
    """Full-text search queries across products and customers."""

    __slots__ = ("session",)

    def __init__(self, session: AsyncReadSession) -> None:
        self.session = session

    @classmethod
    def from_session(cls, session: AsyncReadSession) -> "SearchRepository":
        return cls(session)

    # ── Query execution ──

    async def search(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        query_uuid: uuid.UUID | None,
        has_shares_scope: bool,
        has_customers_scope: bool,
        limit: int = 20,
    ) -> list[Any]:
        """Execute a unified search across products and customers.

        Returns raw rows suitable for validation into ``SearchResult``.
        """
        ts_query_simple = func.websearch_to_tsquery("simple", query)
        ts_query_english = func.websearch_to_tsquery("english", query)
        escaped_query = (
            query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        ilike_term = f"%{escaped_query}%"

        workspace_subquery = (
            select(Workspace.id)
            .join(WorkspaceMembership, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                Workspace.id == workspace_id,
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.deleted_at.is_(None),
            )
        )

        subqueries: list[Select[Any]] = []
        if has_shares_scope:
            products_subquery = self._build_products_subquery(
                workspace_subquery, query_uuid, ts_query_english
            )
            subqueries.append(products_subquery)

        if has_customers_scope:
            customers_subquery = self._build_customers_subquery(
                workspace_subquery, query_uuid, ts_query_simple, ilike_term
            )
            subqueries.append(customers_subquery)

        if not subqueries:
            return []

        union_query = union_all(*subqueries).subquery()

        final_query = (
            select(union_query).order_by(union_query.c.rank.desc()).limit(limit)
        )

        result = await self.session.execute(final_query)
        return list(result.all())

    # ── Private helpers ──

    @staticmethod
    def _build_products_subquery(
        workspace_subquery: Select[tuple[uuid.UUID]],
        query_uuid: uuid.UUID | None,
        ts_query_english: ColumnElement[Any],
    ) -> Select[Any]:
        rank_expr = func.ts_rank(Share.search_vector, ts_query_english)

        stmt = select(
            Share.id,
            literal("share").label("type"),
            rank_expr.label("rank"),
            Share.name.label("name"),
            Share.description.label("description"),
            literal(None).cast(String).label("email"),
        ).where(
            Share.workspace_id.in_(workspace_subquery),
            Share.deleted_at.is_(None),
        )

        if query_uuid:
            stmt = stmt.where(Share.id == query_uuid)
        else:
            stmt = stmt.where(Share.search_vector.op("@@")(ts_query_english))

        return stmt

    @staticmethod
    def _build_customers_subquery(
        workspace_subquery: Select[tuple[uuid.UUID]],
        query_uuid: uuid.UUID | None,
        ts_query_simple: ColumnElement[Any],
        ilike_term: str,
    ) -> Select[Any]:
        rank_expr = func.ts_rank(Customer.search_vector, ts_query_simple)

        stmt = select(
            Customer.id,
            literal("customer").label("type"),
            rank_expr.label("rank"),
            Customer.name.label("name"),
            literal(None).cast(String).label("description"),
            Customer.email.label("email"),
        ).where(
            Customer.workspace_id.in_(workspace_subquery),
            Customer.deleted_at.is_(None),
        )

        if query_uuid:
            stmt = stmt.where(Customer.id == query_uuid)
        else:
            stmt = stmt.where(
                or_(
                    Customer.search_vector.op("@@")(ts_query_simple),
                    Customer.email.ilike(ilike_term),
                )
            )

        return stmt
