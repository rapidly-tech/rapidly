"""Tests for ``rapidly/analytics/event_type/queries.py``.

Five load-bearing surfaces:

- ``get_readable_statement`` enforces tenant scope: USER →
  workspaces with active membership; WORKSPACE → own workspace
  only. Drift would leak event-type catalogues across tenants.
- ``get_by_name_and_workspace`` matches on name + workspace +
  ``deleted_at IS NULL``. Drift to drop the workspace filter
  would let one workspace's event types leak into another's
  lookup; drift to drop the soft-delete filter would re-surface
  archived event types.
- ``get_by_names_and_workspace`` returns empty dict on empty
  input (no SQL emitted) — drift to always-query would emit
  ``IN ()`` SQL that Postgres rejects.
- ``update_label`` is a NO-OP when both fields are None
  (returns the existing event_type unchanged) — drift to
  always-update would touch ``modified_at`` on every call.
- ``get_or_create`` recovers from concurrent-create races: the
  IntegrityError-after-flush path rolls back the nested
  transaction and re-fetches by name (the other process won the
  race). Drift to drop the recovery would 500 on every parallel
  event-creation race.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from rapidly.analytics.event_type.queries import EventTypeRepository


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestReadableStatement:
    async def test_user_principal_filters_by_membership(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = EventTypeRepository(session=MagicMock())
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = uuid4()

        monkeypatch.setattr(
            "rapidly.analytics.event_type.queries.is_user_principal",
            lambda p: True,
        )
        monkeypatch.setattr(
            "rapidly.analytics.event_type.queries.is_workspace_principal",
            lambda p: False,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).lower()
        assert "workspace_memberships.workspace_id" in sql
        assert "workspace_memberships.user_id" in sql
        assert "workspace_memberships.deleted_at is null" in sql

    async def test_workspace_principal_filters_to_own_workspace_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = EventTypeRepository(session=MagicMock())
        target = uuid4()
        principal = MagicMock()
        principal.subject = MagicMock()
        principal.subject.id = target

        monkeypatch.setattr(
            "rapidly.analytics.event_type.queries.is_user_principal",
            lambda p: False,
        )
        monkeypatch.setattr(
            "rapidly.analytics.event_type.queries.is_workspace_principal",
            lambda p: True,
        )

        stmt = repo.get_readable_statement(principal)
        sql = _compile(stmt).replace("-", "")
        assert target.hex in sql


@pytest.mark.asyncio
class TestGetByNameAndWorkspace:
    async def test_filters_on_name_workspace_and_deleted_at(self) -> None:
        repo = EventTypeRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.scalar_one_or_none.return_value = None
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        target = uuid4()
        await repo.get_by_name_and_workspace("checkout.completed", target)

        sql = _compile(captured["stmt"]).lower()
        assert "event_types.name = 'checkout.completed'" in sql
        assert target.hex in sql.replace("-", "")
        assert "event_types.deleted_at is null" in sql


@pytest.mark.asyncio
class TestGetByNamesAndWorkspace:
    async def test_empty_names_returns_empty_dict_no_sql(self) -> None:
        # Pin: drift to always-query would emit ``IN ()`` SQL
        # that Postgres rejects on every empty-input call.
        repo = EventTypeRepository(session=MagicMock())
        repo.session.execute = AsyncMock()  # type: ignore[method-assign]

        out = await repo.get_by_names_and_workspace([], uuid4())

        assert out == {}
        repo.session.execute.assert_not_called()

    async def test_non_empty_names_uses_in_clause(self) -> None:
        repo = EventTypeRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.scalars.return_value.all.return_value = []
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        await repo.get_by_names_and_workspace(["a", "b"], uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "event_types.name in" in sql
        assert "'a'" in sql
        assert "'b'" in sql


@pytest.mark.asyncio
class TestUpdateLabel:
    async def test_no_op_when_both_fields_none(self) -> None:
        # Pin: drift to always-update would touch modified_at on
        # every call (turns this into a write-on-read).
        repo = EventTypeRepository(session=MagicMock())
        repo.update = AsyncMock()  # type: ignore[method-assign]

        et = MagicMock()
        out = await repo.update_label(et)

        assert out is et
        repo.update.assert_not_called()

    async def test_only_label_provided_updates_label_only(self) -> None:
        repo = EventTypeRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _update(obj: Any, *, update_dict: dict[str, Any]) -> Any:
            captured["update_dict"] = update_dict
            return obj

        repo.update = AsyncMock(side_effect=_update)  # type: ignore[method-assign]

        et = MagicMock()
        await repo.update_label(et, label="Checkout completed")

        assert captured["update_dict"] == {"label": "Checkout completed"}

    async def test_only_selector_provided_updates_selector_only(self) -> None:
        repo = EventTypeRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _update(obj: Any, *, update_dict: dict[str, Any]) -> Any:
            captured["update_dict"] = update_dict
            return obj

        repo.update = AsyncMock(side_effect=_update)  # type: ignore[method-assign]

        et = MagicMock()
        await repo.update_label(et, label_property_selector="$.product")

        assert captured["update_dict"] == {"label_property_selector": "$.product"}


@pytest.mark.asyncio
class TestGetOrCreateRaceRecovery:
    async def test_returns_existing_when_match(self) -> None:
        # Pin: clean cache hit doesn't add+flush.
        repo = EventTypeRepository(session=MagicMock())
        existing = MagicMock()
        repo.get_by_name_and_workspace = AsyncMock(return_value=existing)  # type: ignore[method-assign]

        out = await repo.get_or_create("foo", uuid4())
        assert out is existing

    async def test_integrity_error_falls_back_to_refetch(self) -> None:
        # Pin: when the flush hits a unique-constraint race
        # (another worker created the same name concurrently),
        # the nested transaction rolls back and we re-fetch by
        # name. Drift to drop the recovery would 500 on every
        # parallel event-creation race.
        repo = EventTypeRepository(session=MagicMock())

        # First lookup: misses.
        # Second lookup (after IntegrityError): hits the
        # winner's row.
        existing = MagicMock()
        repo.get_by_name_and_workspace = AsyncMock(  # type: ignore[method-assign]
            side_effect=[None, existing]
        )

        nested_tx = MagicMock()
        nested_tx.rollback = AsyncMock()
        repo.session.begin_nested = AsyncMock(return_value=nested_tx)  # type: ignore[method-assign]
        repo.session.flush = AsyncMock(  # type: ignore[method-assign]
            side_effect=IntegrityError("statement", {}, Exception("dup"))
        )

        out = await repo.get_or_create("foo", uuid4())

        assert out is existing
        nested_tx.rollback.assert_called_once()

    async def test_integrity_error_with_no_winner_re_raises(self) -> None:
        # Pin: when the IntegrityError is NOT due to a race
        # (still no row after rollback + re-fetch), re-raise
        # the original error rather than swallow.
        repo = EventTypeRepository(session=MagicMock())

        repo.get_by_name_and_workspace = AsyncMock(side_effect=[None, None])  # type: ignore[method-assign]

        nested_tx = MagicMock()
        nested_tx.rollback = AsyncMock()
        repo.session.begin_nested = AsyncMock(return_value=nested_tx)  # type: ignore[method-assign]
        repo.session.flush = AsyncMock(  # type: ignore[method-assign]
            side_effect=IntegrityError("statement", {}, Exception("real bug"))
        )

        with pytest.raises(IntegrityError):
            await repo.get_or_create("foo", uuid4())
