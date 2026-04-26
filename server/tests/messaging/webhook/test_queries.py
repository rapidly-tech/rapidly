"""Tests for ``rapidly/messaging/webhook/queries.py``.

Six load-bearing surfaces across three repositories:

- ``WebhookEventRepository.get_all_undelivered`` LEFT JOINs
  ``WebhookDelivery`` and filters to ``delivery.id IS NULL``
  (events that have NEVER been delivered) AND
  ``payload IS NOT NULL`` (drop archived) AND ``skipped IS
  FALSE`` (drop manually-skipped). Drift on any branch would
  cause the retry worker to re-deliver already-shipped events
  OR loop on archived/skipped ones.
- ``WebhookEventRepository.get_recent_by_endpoint`` filters to
  COMPLETED events (``succeeded IS NOT NULL``) and orders DESC.
  Drift would surface pending retries in the "recent deliveries"
  list and confuse merchants.
- ``WebhookEventRepository.skip_pending_by_endpoint`` UPDATEs
  only rows with ``succeeded IS NULL`` AND ``skipped IS FALSE``
  AND ``deleted_at IS NULL``. Drift would re-touch already-
  skipped rows or skip rows that already succeeded (silently
  rewriting history).
- ``WebhookEventRepository.archive_payloads`` uses a batch
  subquery (``ORDER BY created_at ASC LIMIT N``) to null
  payloads in chunks. Drift to DESC would archive the newest
  first; drift to drop the LIMIT would lock the table on huge
  archive runs.
- ``WebhookDeliveryRepository.apply_list_filters`` HTTP-code-
  class filter maps "2xx" → `[200, 300)`, "3xx" → `[300, 400)`,
  etc. Drift to bounds-off-by-one would mis-categorise every
  delivery in the admin's audit list.
- ``WebhookEndpointRepository.get_active_for_event`` requires
  ``enabled=True`` AND ``events @> [<event>]`` JSONB containment.
  Drift to drop ``enabled`` would deliver to disabled endpoints;
  drift to drop the containment would fan out every event to
  every endpoint (DDoS the merchant).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.messaging.webhook.queries import (
    WebhookDeliveryRepository,
    WebhookEndpointRepository,
    WebhookEventRepository,
)
from rapidly.models.webhook_endpoint import WebhookEventType


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestEventGetAllUndelivered:
    async def test_left_join_and_three_predicates(self) -> None:
        # Pin: undelivered = no delivery row + payload set +
        # not skipped. Drift on any predicate would break the
        # retry worker.
        repo = WebhookEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_all_undelivered()

        sql = _compile(captured["stmt"]).lower()
        assert "left outer join webhook_deliveries" in sql
        assert "webhook_deliveries.id is null" in sql
        assert "webhook_events.payload is not null" in sql
        assert "webhook_events.skipped is false" in sql

    async def test_optional_older_than_filter(self) -> None:
        repo = WebhookEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_all_undelivered(older_than=datetime(2026, 1, 1, tzinfo=UTC))

        sql = _compile(captured["stmt"]).lower()
        assert "webhook_events.created_at <" in sql
        assert "2026-01-01" in sql


@pytest.mark.asyncio
class TestEventGetRecentByEndpoint:
    async def test_only_completed_events_desc(self) -> None:
        # Pin: ``succeeded IS NOT NULL`` filters out pending
        # retries. Drift would surface in-flight events in the
        # "recent deliveries" list.
        repo = WebhookEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_recent_by_endpoint(uuid4(), limit=10)

        sql = _compile(captured["stmt"]).lower()
        assert "webhook_events.succeeded is not null" in sql
        assert "order by webhook_events.created_at desc" in sql
        assert "limit 10" in sql


@pytest.mark.asyncio
class TestSkipPendingByEndpoint:
    async def test_three_predicate_update(self) -> None:
        # Pin: only update rows where succeeded IS NULL AND
        # skipped IS FALSE AND deleted_at IS NULL. Drift would
        # re-touch already-skipped rows / skip already-succeeded
        # rows.
        repo = WebhookEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.rowcount = 0
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        await repo.skip_pending_by_endpoint(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("update webhook_events")
        assert "webhook_events.succeeded is null" in sql
        assert "webhook_events.skipped is false" in sql
        assert "webhook_events.deleted_at is null" in sql


@pytest.mark.asyncio
class TestArchivePayloadsBatched:
    async def test_batch_subquery_orders_oldest_first(self) -> None:
        # Pin: ASC + LIMIT — archive the OLDEST events in
        # batches. Drift to DESC would archive newest first
        # (wrong direction); drift to drop LIMIT could lock
        # the table on huge archive runs.
        repo = WebhookEventRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.rowcount = 0
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        await repo.archive_payloads(
            older_than=datetime(2026, 1, 1, tzinfo=UTC),
            batch_size=100,
        )

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("update webhook_events")
        assert "order by webhook_events.created_at asc" in sql
        assert "limit 100" in sql


class TestDeliveryListFiltersHttpCodeClass:
    def _stmt(self, **kw: Any) -> str:
        repo = WebhookDeliveryRepository(session=MagicMock())
        stmt = repo.get_base_statement()
        stmt = repo.apply_list_filters(stmt, **kw)
        return _compile(stmt).lower()

    def test_2xx_filter_bounds(self) -> None:
        # Pin: 2xx → [200, 300). Drift would mis-categorise
        # every delivery in the audit list.
        sql = self._stmt(http_code_class="2xx")
        assert ">= 200" in sql
        assert "< 300" in sql

    def test_3xx_filter_bounds(self) -> None:
        sql = self._stmt(http_code_class="3xx")
        assert ">= 300" in sql
        assert "< 400" in sql

    def test_4xx_filter_bounds(self) -> None:
        sql = self._stmt(http_code_class="4xx")
        assert ">= 400" in sql
        assert "< 500" in sql

    def test_5xx_filter_bounds(self) -> None:
        sql = self._stmt(http_code_class="5xx")
        assert ">= 500" in sql
        assert "< 600" in sql

    def test_query_uses_escape_like(self) -> None:
        # Pin: drift to drop escape_like would let an admin's
        # typed `%` flood the audit list.
        sql = self._stmt(query="50%off")
        assert r"50\%off" in sql


@pytest.mark.asyncio
class TestEndpointGetActiveForEvent:
    async def test_filters_enabled_and_subscribed(self) -> None:
        # Pin: BOTH enabled AND JSONB-contains the event type.
        # Drift to drop enabled would deliver to disabled
        # endpoints; drift to drop the containment would fan out
        # every event to every endpoint (DDoS the merchant).
        repo = WebhookEndpointRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            r = MagicMock()
            r.scalars.return_value.unique.return_value.all.return_value = []
            return r

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]
        await repo.get_active_for_event(WebhookEventType.customer_created, uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "webhook_endpoints.enabled is true" in sql
        # JSONB containment operator surfaces in the rendered
        # SQL.
        assert "webhook_endpoints.events @>" in sql
        # And the event-type literal appears.
        assert "customer.created" in sql
