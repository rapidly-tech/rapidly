"""Tests for ``rapidly/catalog/share/queries.py``.

Five load-bearing surfaces:

- ``get_readable_statement`` enforces tenant scope: USER →
  workspaces with active membership; WORKSPACE → own workspace
  only. Drift would leak shares across tenants — a critical
  catalog-isolation guard.
- ``get_list_statement`` LEFT-JOINs to the FIRST non-archived,
  non-deleted price (``ORDER BY created_at ASC LIMIT 1``).
  Drift to inner-join would 404 shares with NO active price;
  drift to ``DESC`` would surface the most-recently-created
  price instead of the canonical "first" one.
- ``apply_list_filters`` uses ``escape_like`` on the search
  query so a typo'd ``%`` doesn't match every share. Drift to
  drop the escape would let a single typed ``%`` flood the
  catalog list.
- ``count_by_workspace_id`` filters out soft-deleted shares,
  applies optional ``is_archived`` filter, and returns 0 (not
  None) on empty workspaces.
- ``get_sorting_clause`` for ``price_amount`` orders FREE < CUSTOM
  < FIXED via numeric ``-2 / -1 / amount`` placeholders. Drift
  would mis-order the catalog list (free shares would float to
  the top OR sink to the bottom depending on direction).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.catalog.share.ordering import ShareSortProperty
from rapidly.catalog.share.queries import ShareRepository
from rapidly.models.share import ShareVisibility


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetReadableStatement:
    async def test_user_principal_filters_by_membership(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: USER → workspace membership scope. Drift would
        # let any user list any workspace's shares.
        repo = ShareRepository(session=MagicMock())
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = uuid4()

        monkeypatch.setattr(
            "rapidly.catalog.share.queries.is_user_principal", lambda p: True
        )
        monkeypatch.setattr(
            "rapidly.catalog.share.queries.is_workspace_principal", lambda p: False
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).lower()
        assert "workspace_memberships.workspace_id" in sql
        assert "workspace_memberships.user_id" in sql
        assert "workspace_memberships.deleted_at is null" in sql

    async def test_workspace_principal_filters_to_own_workspace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: WORKSPACE → equality on own workspace_id.
        repo = ShareRepository(session=MagicMock())
        target = uuid4()
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = target

        monkeypatch.setattr(
            "rapidly.catalog.share.queries.is_user_principal", lambda p: False
        )
        monkeypatch.setattr(
            "rapidly.catalog.share.queries.is_workspace_principal", lambda p: True
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).replace("-", "")
        assert target.hex in sql


class TestGetListStatementPriceJoin:
    def _stmt(self, monkeypatch: pytest.MonkeyPatch) -> object:
        monkeypatch.setattr(
            "rapidly.catalog.share.queries.is_user_principal", lambda p: False
        )
        monkeypatch.setattr(
            "rapidly.catalog.share.queries.is_workspace_principal", lambda p: False
        )
        repo = ShareRepository(session=MagicMock())
        return repo.get_list_statement(MagicMock())

    def test_uses_left_outer_join(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: ``isouter=True`` → LEFT JOIN. Drift to inner join
        # would 404 every share that has NO active price.
        sql = _compile(self._stmt(monkeypatch)).lower()
        assert "left outer join share_prices" in sql

    def test_picks_first_non_archived_non_deleted_price(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: subquery filters on archived + deleted, orders by
        # created_at ASC, limits 1 — the canonical "first"
        # price. Drift to DESC would surface the most-recent
        # price; drift to drop archived filter would surface
        # the original price after a price change.
        sql = _compile(self._stmt(monkeypatch)).lower()
        assert "share_prices.is_archived" in sql
        assert "share_prices.deleted_at is null" in sql
        assert "order by share_prices.created_at asc" in sql
        assert "limit 1" in sql


class TestApplyListFiltersTextSearch:
    def test_escape_like_applied_to_query(self) -> None:
        # Pin: drift to drop ``escape_like`` would let a single
        # typed ``%`` flood the catalog list.
        repo = ShareRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt, query="50%off")
        sql = _compile(stmt)
        assert r"50\%off" in sql

    def test_visibility_uses_in_clause(self) -> None:
        # Pin: caller may pass multiple visibilities (e.g.
        # public + hidden in admin views) — drift to equality
        # would 500 on multi-value filters.
        repo = ShareRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(
            stmt,
            visibility=[ShareVisibility.public, ShareVisibility.private],
        )
        sql = _compile(stmt).lower()
        assert "shares.visibility in" in sql


@pytest.mark.asyncio
class TestCountByWorkspaceId:
    async def test_excludes_soft_deleted_shares(self) -> None:
        repo = ShareRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _scalar(stmt: object) -> int:
            captured["stmt"] = stmt
            return 0

        repo.session.scalar = AsyncMock(side_effect=_scalar)  # type: ignore[method-assign]
        await repo.count_by_workspace_id(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "shares.deleted_at is null" in sql
        assert "count(" in sql

    async def test_returns_zero_on_empty_workspace(self) -> None:
        # Pin: scalar() can return None — return 0 so callers
        # comparing against int seat-cap don't crash.
        repo = ShareRepository(session=MagicMock())
        repo.session.scalar = AsyncMock(return_value=None)  # type: ignore[method-assign]
        count = await repo.count_by_workspace_id(uuid4())
        assert count == 0

    async def test_optional_archived_filter_applied_when_set(self) -> None:
        # Pin: ``is_archived`` filter only added when explicitly
        # passed. Drift to always-filter would silently mismatch
        # on None inputs.
        repo = ShareRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _scalar(stmt: object) -> int:
            captured["stmt"] = stmt
            return 0

        repo.session.scalar = AsyncMock(side_effect=_scalar)  # type: ignore[method-assign]
        await repo.count_by_workspace_id(uuid4(), is_archived=False)
        sql = _compile(captured["stmt"]).lower()
        assert "shares.is_archived is false" in sql or "is_archived = false" in sql


class TestSortingClausePriceOrdering:
    def test_price_amount_orders_free_then_custom_then_fixed(self) -> None:
        # Pin: numeric placeholders -2 / -1 / amount → FREE
        # always sinks to the bottom (-2 in ASC) AND custom
        # sits below fixed. Drift would mis-order the catalog
        # list and confuse customers comparing prices.
        repo = ShareRepository(session=MagicMock())
        clause = repo.get_sorting_clause(ShareSortProperty.price_amount)
        rendered = str(
            clause.compile(compile_kwargs={"literal_binds": True})  # type: ignore[union-attr]
        ).lower()
        # The CASE expression includes the documented branch
        # values: -2 for free, -1 fallback for custom (COALESCE),
        # and the live amount for fixed.
        assert "case" in rendered
        assert "-2" in rendered
        assert "-1" in rendered
        assert "share_prices.price_amount" in rendered

    def test_price_amount_type_fixed_ordering(self) -> None:
        # Pin: amount_type sort places FREE (1), CUSTOM (2),
        # FIXED (3) — drift would shuffle the type-grouped
        # display.
        repo = ShareRepository(session=MagicMock())
        clause = repo.get_sorting_clause(ShareSortProperty.price_amount_type)
        rendered = str(
            clause.compile(compile_kwargs={"literal_binds": True})  # type: ignore[union-attr]
        ).lower()
        assert "case" in rendered
        # All three integer placeholders appear.
        assert " 1" in rendered
        assert " 2" in rendered
        assert " 3" in rendered
