"""Tests for ``rapidly/analytics/external_event/queries.py``.

Five load-bearing surfaces:

- ``get_by_source_and_id`` filters on BOTH ``source`` and ``id``
  — drift to drop ``source`` would surface a colliding event
  from a different upstream provider (Stripe `evt_*` vs.
  Razorpay event id).
- ``get_by_source_and_id(with_for_update=True)`` adds
  ``FOR UPDATE`` so worker code can lock the row before
  marking handled (drift to drop would let two workers race
  on the same external event and double-process).
- ``get_by_source_and_external_id`` matches on source +
  the upstream's id string (e.g. ``evt_xyz``) — drift to drop
  source would let a Stripe event id match a Razorpay row.
- ``get_all_unhandled`` filters ``handled_at IS NULL``;
  optional ``older_than`` adds ``created_at < cutoff`` for
  staleness-based polling.
- ``delete_before`` HARD-deletes only HANDLED rows older than
  the cutoff. Drift to drop the ``handled_at IS NOT NULL``
  filter would catastrophically delete unprocessed events
  during cleanup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.analytics.external_event.queries import ExternalEventRepository
from rapidly.models.external_event import ExternalEventSource


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetBySourceAndId:
    async def test_filters_on_both_source_and_id(self) -> None:
        # Pin: drift to drop ``source`` would surface a
        # colliding id from a different upstream provider.
        repo = ExternalEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]

        target = uuid4()
        await repo.get_by_source_and_id(ExternalEventSource.stripe, target)

        sql = _compile(captured["stmt"]).lower()
        assert "external_events.source" in sql
        assert "'stripe'" in sql
        assert target.hex in sql.replace("-", "")

    async def test_with_for_update_adds_locking_clause(self) -> None:
        # Pin: workers race-resolve via SELECT ... FOR UPDATE.
        # Drift to drop the locking would let two workers
        # process the same external event concurrently.
        repo = ExternalEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_source_and_id(
            ExternalEventSource.stripe, uuid4(), with_for_update=True
        )

        sql = _compile(captured["stmt"]).lower()
        assert "for update" in sql

    async def test_default_omits_for_update(self) -> None:
        repo = ExternalEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_source_and_id(ExternalEventSource.stripe, uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "for update" not in sql


@pytest.mark.asyncio
class TestGetBySourceAndExternalId:
    async def test_filters_on_both_source_and_external_id(self) -> None:
        # Pin: source pair guard. Drift to drop source would
        # let a Stripe ``evt_xyz`` match a Razorpay row when
        # other PSPs are added.
        repo = ExternalEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_source_and_external_id(ExternalEventSource.stripe, "evt_xyz")

        sql = _compile(captured["stmt"]).lower()
        assert "'stripe'" in sql
        assert "external_events.external_id = 'evt_xyz'" in sql


@pytest.mark.asyncio
class TestGetAllUnhandled:
    async def test_filters_handled_at_is_null(self) -> None:
        repo = ExternalEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_all_unhandled()

        sql = _compile(captured["stmt"]).lower()
        assert "external_events.handled_at is null" in sql

    async def test_optional_older_than_filter(self) -> None:
        repo = ExternalEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_all_unhandled(older_than=datetime(2026, 1, 1, tzinfo=UTC))

        sql = _compile(captured["stmt"]).lower()
        assert "external_events.created_at <" in sql
        assert "2026-01-01" in sql


@pytest.mark.asyncio
class TestDeleteBefore:
    async def test_only_deletes_handled_rows(self) -> None:
        # Pin: ``handled_at IS NOT NULL`` AND ``created_at <
        # cutoff``. Drift to drop the handled filter would
        # catastrophically delete unprocessed events during
        # cleanup (data loss before they're handled).
        repo = ExternalEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        cutoff = datetime(2026, 1, 1, tzinfo=UTC)
        await repo.delete_before(cutoff)

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("delete from external_events")
        assert "external_events.handled_at is not null" in sql
        assert "external_events.created_at <" in sql
        assert "2026-01-01" in sql
