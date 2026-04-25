"""Tests for ``rapidly/sharing/storefront/queries.py``.

The public-facing storefront. Three load-bearing surfaces:

- ``get_by_slug`` ONLY returns workspaces that pass the FOUR
  visibility gates: not soft-deleted, not blocked, the slug
  matches, AND ``storefront_enabled`` is ``True``. Drift to drop
  any of these would expose hidden / suspended workspaces to
  the public storefront — a privacy + brand-reputation hazard.
- ``list_public_file_shares`` returns only ACTIVE PAID shares
  (``status == active`` AND ``price_cents > 0``). Drift would
  surface drafts, archived, or free-tier shares on the public
  page; the ``LIMIT 100`` is also pinned so a workspace with
  thousands of shares can't OOM the storefront page render.
- ``list_customers`` scopes by workspace_id AND
  ``deleted_at IS NULL``. Drift to drop the workspace filter
  would leak every workspace's customer list through the
  storefront customer-portal endpoints.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.sharing.storefront.queries import StorefrontRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetBySlugVisibilityGates:
    async def test_filters_match_documented_four_gates(self) -> None:
        # Pin: deleted_at IS NULL, blocked_at IS NULL, slug match,
        # AND storefront_enabled=True. Drift to drop any would
        # expose hidden / suspended workspaces.
        repo = StorefrontRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _capture(stmt: object) -> object:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_slug("acme")

        sql = _compile(captured["stmt"]).lower()
        # The four gates surface as four WHERE clauses (and the
        # slug literal).
        assert "deleted_at is null" in sql
        assert "blocked_at is null" in sql
        assert "slug = 'acme'" in sql
        # storefront_enabled is a hybrid property backed by the
        # ``profile_settings['enabled']`` JSON key. Pinning the
        # ``is true`` literal so drift to ``False`` default would
        # invert the gate.
        assert "profile_settings" in sql
        assert "enabled" in sql
        assert "is true" in sql or "= true" in sql or "= 1" in sql


@pytest.mark.asyncio
class TestListPublicFileShares:
    async def _captured_stmt(self) -> object:
        repo = StorefrontRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _exec(stmt: object) -> object:
            captured["stmt"] = stmt
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = []
            result = MagicMock()
            result.scalars.return_value = scalars_mock
            return result

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        await repo.list_public_file_shares(uuid4())
        return captured["stmt"]

    async def test_filters_to_active_status(self) -> None:
        # Pin: only ``status == active`` shares appear publicly.
        # Drift would surface drafts on the storefront page.
        sql = _compile(await self._captured_stmt()).lower()
        assert "status" in sql
        assert "active" in sql

    async def test_filters_to_paid_shares_only(self) -> None:
        # Pin: ``price_cents IS NOT NULL`` AND ``price_cents > 0``.
        # Drift would surface free shares on the storefront,
        # which is reserved for paid catalog only.
        sql = _compile(await self._captured_stmt()).lower()
        assert "price_cents" in sql
        assert "is not null" in sql
        assert "> 0" in sql

    async def test_orders_by_created_at_desc(self) -> None:
        # Pin: most-recent shares at the top of the storefront.
        # Drift to ASC would bury fresh listings.
        sql = _compile(await self._captured_stmt()).lower()
        assert "order by file_share_sessions.created_at desc" in sql

    async def test_limit_pinned_to_100(self) -> None:
        # Pin: bounded result set. Drift to no LIMIT (or a higher
        # one) would let a workspace with thousands of shares OOM
        # the storefront page render.
        sql = _compile(await self._captured_stmt()).lower()
        assert "limit 100" in sql

    async def test_excludes_soft_deleted_shares(self) -> None:
        # Pin: a customer who shared something then deleted it
        # should not see ghost listings on the public page.
        sql = _compile(await self._captured_stmt()).lower()
        assert "deleted_at is null" in sql


@pytest.mark.asyncio
class TestListCustomers:
    async def test_scopes_by_workspace_id_and_excludes_deleted(self) -> None:
        # Pin: workspace_id privacy guard + soft-delete filter.
        # Drift to drop the workspace filter would leak every
        # workspace's customer list through the storefront.
        repo = StorefrontRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _exec(stmt: object) -> object:
            captured["stmt"] = stmt
            result = MagicMock()
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = []
            result.scalars.return_value = scalars_mock
            # paginate also calls .scalar() for COUNT
            result.scalar.return_value = 0
            return result

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        from rapidly.core.pagination import PaginationParams

        workspace = MagicMock()
        workspace.id = uuid4()
        workspace_id_str = str(workspace.id).replace("-", "")

        await repo.list_customers(
            workspace, pagination=PaginationParams(page=1, limit=10)
        )

        # The captured statement is the SELECT (not the COUNT
        # variant) — assert workspace + deleted_at filters appear.
        sql = _compile(captured["stmt"]).replace("-", "").lower()
        assert "customers.workspace_id" in sql
        # The literal-bound UUID (dashless) appears in the WHERE.
        assert workspace_id_str in sql
        assert "deleted_at is null" in sql
