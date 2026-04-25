"""Tests for ``rapidly/platform/workspace_membership/queries.py``.

Five load-bearing surfaces:

- ``get_member_count`` filters to ACTIVE memberships only
  (``deleted_at IS NULL``). Drift would inflate the count with
  former members and surface as wrong seat-billing on every
  workspace's plan page.
- ``list_by_user_id`` excludes soft-deleted memberships and
  orders by ``created_at ASC`` (oldest workspace first in the
  user's switcher). Drift to DESC would shuffle the user's
  workspace dropdown on every login.
- All read methods that hydrate a membership eagerly load
  ``user`` and ``workspace`` (drift to lazy-load would N+1 every
  list-page render).
- ``remove_member`` is a SOFT DELETE (sets ``deleted_at`` via
  UPDATE) — drift to a hard DELETE would cascade-orphan
  audit-log rows referencing the membership and break
  retroactive analytics.
- ``remove_member`` only updates rows where ``deleted_at IS NULL``
  (drift would re-stamp the timestamp on already-deleted rows
  and corrupt the historical record).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.platform.workspace_membership.queries import (
    WorkspaceMembershipRepository,
)


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestMemberCountFiltersDeleted:
    async def test_excludes_soft_deleted_rows(self) -> None:
        # Pin: only ACTIVE memberships count toward seat-billing.
        # Drift would inflate the count and over-bill or block
        # the "add member" flow on a stale seat-cap check.
        repo = WorkspaceMembershipRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _exec(stmt: object) -> object:
            captured["stmt"] = stmt
            result = MagicMock()
            result.scalar.return_value = 0
            return result

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        await repo.get_member_count(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "deleted_at is null" in sql
        assert "count(" in sql

    async def test_zero_when_no_rows(self) -> None:
        # Pin: ``None`` from scalar() returns 0 (not None) — the
        # caller's seat-comparison won't crash on freshly-created
        # workspaces.
        repo = WorkspaceMembershipRepository(session=MagicMock())

        async def _exec(stmt: object) -> object:
            result = MagicMock()
            result.scalar.return_value = None
            return result

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        count = await repo.get_member_count(uuid4())
        assert count == 0


class TestListByUserIdOrdering:
    def test_orders_by_created_at_asc(self) -> None:
        # Pin: oldest workspace first in the user's switcher.
        # Drift to DESC would shuffle the user's workspace
        # dropdown on every login (UX nightmare).
        stmt = WorkspaceMembershipRepository._get_list_by_user_id_query(
            uuid4(), ordered=True
        )
        sql = _compile(stmt).lower()
        assert "order by workspace_memberships.created_at asc" in sql

    def test_excludes_soft_deleted_rows(self) -> None:
        # Pin: never surface former workspaces in the user's
        # switcher.
        stmt = WorkspaceMembershipRepository._get_list_by_user_id_query(uuid4())
        sql = _compile(stmt).lower()
        assert "deleted_at is null" in sql

    def test_unordered_query_skips_order_by(self) -> None:
        # Pin: when ``ordered=False`` (used by COUNT path), no
        # ORDER BY is emitted (saves a redundant SQL operation
        # on the count subquery).
        stmt = WorkspaceMembershipRepository._get_list_by_user_id_query(
            uuid4(), ordered=False
        )
        sql = _compile(stmt).lower()
        assert "order by" not in sql


@pytest.mark.asyncio
class TestRemoveMemberIsSoftDelete:
    async def test_uses_update_with_deleted_at_timestamp(self) -> None:
        # Pin: soft delete via UPDATE (sets deleted_at). Drift
        # to a hard DELETE would cascade-orphan audit-log rows
        # referencing the membership and break retroactive
        # analytics on who-removed-whom.
        repo = WorkspaceMembershipRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _exec(stmt: object) -> object:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        await repo.remove_member(uuid4(), uuid4())

        sql = _compile(captured["stmt"]).lower()
        # UPDATE statement (NOT DELETE).
        assert sql.startswith("update workspace_memberships")
        assert "deleted_at" in sql

    async def test_only_updates_rows_where_deleted_at_is_null(self) -> None:
        # Pin: skip rows that are already deleted. Drift would
        # re-stamp the timestamp on already-removed members and
        # corrupt the historical record (when did Alice ACTUALLY
        # leave the workspace?).
        repo = WorkspaceMembershipRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _exec(stmt: object) -> object:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        await repo.remove_member(uuid4(), uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "deleted_at is null" in sql

    async def test_scopes_by_user_and_workspace(self) -> None:
        # Pin: privacy guard. The UPDATE MUST scope by BOTH
        # user_id AND workspace_id, otherwise a buggy caller
        # could remove an entire workspace's membership in a
        # single call.
        repo = WorkspaceMembershipRepository(session=MagicMock())
        captured: dict[str, object] = {}

        async def _exec(stmt: object) -> object:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        user_id = uuid4()
        workspace_id = uuid4()
        await repo.remove_member(user_id, workspace_id)

        sql = _compile(captured["stmt"]).replace("-", "")
        assert user_id.hex in sql
        assert workspace_id.hex in sql
