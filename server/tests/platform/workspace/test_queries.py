"""Tests for ``rapidly/platform/workspace/queries.py``.

Five load-bearing surfaces:

- ``slug_exists`` INCLUDES soft-deleted workspaces (drift to
  ``include_deleted=False`` would let a soft-deleted slug be
  reused — audit links to ``/workspaces/<slug>`` would silently
  resolve to the wrong workspace after the original was
  recreated).
- ``get_by_id`` defaults to excluding blocked + deleted but
  ``include_blocked=True`` admin override drops only the
  blocked filter.
- ``get_accessible_by_id`` requires the user to have an ACTIVE
  membership (membership ``deleted_at IS NULL``). Drift to drop
  the membership filter would let any user fetch any workspace
  by id.
- ``reactivate_membership`` UPDATEs the row to ``deleted_at=None``
  scoped by BOTH user_id AND workspace_id (drift to drop either
  scope would un-delete the wrong row).
- ``sync_account_status`` maps WorkspaceStatus → Account.Status
  for the FIVE documented transitions; non-mapped statuses (e.g.
  CREATED) emit NO update — drift would leak transient creation
  state into the Account table.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.models import Account
from rapidly.models.workspace import WorkspaceStatus
from rapidly.platform.workspace.queries import WorkspaceRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestSlugExistsIncludesDeleted:
    async def test_query_skips_soft_delete_filter(self) -> None:
        # Pin: drift to filter ``deleted_at IS NULL`` would let a
        # soft-deleted slug be reused; audit / admin links to the
        # original workspace would silently resolve to the
        # replacement.
        repo = WorkspaceRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.slug_exists("acme")

        sql = _compile(captured["stmt"]).lower()
        # The slug equality is present...
        assert "workspaces.slug = 'acme'" in sql
        # ...but the soft-delete filter is NOT (include_deleted=True).
        assert "workspaces.deleted_at is null" not in sql

    async def test_returns_true_when_row_exists(self) -> None:
        repo = WorkspaceRepository(session=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=MagicMock())  # type: ignore[method-assign]
        assert await repo.slug_exists("acme") is True

    async def test_returns_false_when_no_row(self) -> None:
        repo = WorkspaceRepository(session=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=None)  # type: ignore[method-assign]
        assert await repo.slug_exists("acme") is False


@pytest.mark.asyncio
class TestGetByIdGates:
    async def test_default_excludes_blocked(self) -> None:
        # Pin: ``blocked_at IS NULL`` is the default gate. Drift
        # to default-include would surface blocked workspaces in
        # user-facing lookups.
        repo = WorkspaceRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_id(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "workspaces.blocked_at is null" in sql

    async def test_include_blocked_drops_blocked_filter(self) -> None:
        # Pin: admin moderator-detail page sets include_blocked=True
        # — drift to always-filter would 404 every blocked-workspace
        # admin link.
        repo = WorkspaceRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_id(uuid4(), include_blocked=True)

        sql = _compile(captured["stmt"]).lower()
        assert "blocked_at is null" not in sql


@pytest.mark.asyncio
class TestGetAccessibleByIdMembership:
    async def test_filters_by_user_active_membership(self) -> None:
        # Pin: privacy guard. Drift to drop the membership
        # subquery would let any user fetch any workspace by id.
        repo = WorkspaceRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]

        user_id = uuid4()
        workspace_id = uuid4()
        await repo.get_accessible_by_id(workspace_id, user_id)

        sql = _compile(captured["stmt"])
        # The user_id and workspace_id appear in the rendered
        # SQL, and the membership soft-delete filter is present.
        assert user_id.hex in sql.replace("-", "")
        assert workspace_id.hex in sql.replace("-", "")
        assert "workspace_memberships.deleted_at IS NULL" in sql


@pytest.mark.asyncio
class TestReactivateMembership:
    async def test_update_sets_deleted_at_to_none_and_scopes_by_both(self) -> None:
        # Pin: only the matching (user_id, workspace_id) pair is
        # updated. Drift to drop either scope would un-delete the
        # wrong row.
        repo = WorkspaceRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        repo.session.flush = AsyncMock()  # type: ignore[method-assign]

        user_id = uuid4()
        workspace_id = uuid4()
        await repo.reactivate_membership(user_id, workspace_id)

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("update workspace_memberships")
        # Both scopes appear.
        assert user_id.hex in sql.replace("-", "")
        assert workspace_id.hex in sql.replace("-", "")
        # And the value being set is NULL (deleted_at=None).
        assert "deleted_at=null" in sql.replace(" ", "")


@pytest.mark.asyncio
class TestSyncAccountStatusMapping:
    async def test_documented_status_mappings(self) -> None:
        # Pin: 5-entry mapping table (CREATED is INTENTIONALLY
        # NOT in the table — drift to add it would leak a
        # transient state to Account).
        captured: list[Any] = []

        async def _exec(stmt: object) -> Any:
            captured.append(stmt)
            return MagicMock()

        for ws_status, account_status in [
            (WorkspaceStatus.ONBOARDING_STARTED, Account.Status.ONBOARDING_STARTED),
            (WorkspaceStatus.ACTIVE, Account.Status.ACTIVE),
            (WorkspaceStatus.INITIAL_REVIEW, Account.Status.UNDER_REVIEW),
            (WorkspaceStatus.ONGOING_REVIEW, Account.Status.UNDER_REVIEW),
            (WorkspaceStatus.DENIED, Account.Status.DENIED),
        ]:
            captured.clear()
            repo = WorkspaceRepository(session=MagicMock())
            repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

            workspace = MagicMock()
            workspace.account_id = uuid4()
            workspace.status = ws_status

            await repo.sync_account_status(workspace)

            assert len(captured) == 1, ws_status
            sql = _compile(captured[0]).lower()
            # The mapped account_status name appears in the
            # rendered SQL.
            assert account_status.value.lower() in sql

    async def test_no_account_id_short_circuits(self) -> None:
        # Pin: workspaces with no account_id (rare init path)
        # don't trigger an UPDATE. Drift would crash on missing
        # account.
        repo = WorkspaceRepository(session=MagicMock())
        repo.session.execute = AsyncMock()  # type: ignore[method-assign]

        workspace = MagicMock()
        workspace.account_id = None
        workspace.status = WorkspaceStatus.ACTIVE

        await repo.sync_account_status(workspace)

        repo.session.execute.assert_not_called()

    async def test_unmapped_status_emits_no_update(self) -> None:
        # Pin: only the 5 documented statuses fire updates.
        # Drift to fall through would leak transient creation
        # state to the Account table.
        repo = WorkspaceRepository(session=MagicMock())
        repo.session.execute = AsyncMock()  # type: ignore[method-assign]

        workspace = MagicMock()
        workspace.account_id = uuid4()
        workspace.status = WorkspaceStatus.CREATED

        await repo.sync_account_status(workspace)

        repo.session.execute.assert_not_called()
