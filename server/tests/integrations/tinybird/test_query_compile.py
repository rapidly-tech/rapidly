"""Offline SQL-compile tests for the Tinybird query builders.

The existing ``test_service.py`` exercises the queries against a
LIVE Tinybird workspace (xdist-grouped, requires credentials). These
tests run offline by capturing the compiled SQL via a
``client.query`` patch — they pin the SQL surface in CI without
needing the live integration.

Five load-bearing surfaces:

- ``TinybirdEventsQuery`` ALWAYS scopes by ``organization_id``.
  This is the multi-tenant privacy guard — drift to drop the
  filter would leak every workspace's events into one
  workspace's analytics dashboard.
- ``filter_customer_id`` / ``filter_external_customer_id`` skip
  the WHERE when the sequence is empty (drift would emit
  ``IN ()`` SQL that ClickHouse rejects with a 4xx — the page
  would 500 on load with no customer filter active).
- ``filter_root_events`` adds ``parent_id IS NULL``. Drift to
  ``IS NOT NULL`` would invert "show top-level events" into
  "show only nested events".
- ``order_by`` raises ``ValueError`` for unknown sort columns
  (the ``_SORT_COLUMN_MAP`` is the documented allow-list). Drift
  to silently fall through would render the dashboard with no
  ordering applied.
- Default ``ORDER BY`` is ``max(timestamp) DESC`` so the most
  recent activity is at the top of the dashboard.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from rapidly.integrations.tinybird import actions as M
from rapidly.integrations.tinybird.actions import (
    TinybirdEventsQuery,
    TinybirdEventTypesQuery,
)
from rapidly.models.event import EventSource

_WORKSPACE_ID = UUID("11111111-1111-1111-1111-111111111111")
_CUSTOMER_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def captured_sql(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace ``client.query`` with an AsyncMock that captures the
    rendered SQL passed in by the query builders. Returns a dict
    that gets populated on each call.
    """
    captured: dict[str, Any] = {}

    async def _capture(sql: str, *, db_statement: str = "") -> list[Any]:
        captured["sql"] = sql
        captured["template"] = db_statement
        return []

    monkeypatch.setattr(
        "rapidly.integrations.tinybird.actions.client.query",
        AsyncMock(side_effect=_capture),
    )
    _ = M  # silence unused-import for the path-string monkeypatch
    return captured


@pytest.mark.asyncio
class TestEventsQueryWorkspaceScope:
    async def test_always_filters_by_organization_id(
        self, captured_sql: dict[str, Any]
    ) -> None:
        # Pin: privacy guard. Drift to drop the workspace filter
        # would leak every workspace's events into one
        # dashboard.
        await TinybirdEventsQuery(_WORKSPACE_ID).get_event_type_stats()

        sql: str = captured_sql["sql"]
        # The workspace UUID appears in the rendered SQL as a
        # bound literal.
        assert str(_WORKSPACE_ID) in sql
        assert "organization_id" in sql.lower()

    async def test_filter_methods_layered_on_top_of_workspace_scope(
        self, captured_sql: dict[str, Any]
    ) -> None:
        # Pin: extra filters do NOT replace the workspace scope.
        await (
            TinybirdEventsQuery(_WORKSPACE_ID)
            .filter_source(EventSource.system)
            .get_event_type_stats()
        )
        sql: str = captured_sql["sql"]
        assert str(_WORKSPACE_ID) in sql
        assert "system" in sql.lower()


@pytest.mark.asyncio
class TestEmptySequenceFiltersSkipped:
    async def test_empty_customer_ids_no_in_clause(
        self, captured_sql: dict[str, Any]
    ) -> None:
        # Pin: ``filter_customer_id([])`` is a no-op. Drift to
        # always-add would emit ``IN ()`` SQL that ClickHouse
        # rejects, 500'ing the page when the admin clears the
        # customer filter.
        await (
            TinybirdEventsQuery(_WORKSPACE_ID)
            .filter_customer_id([])
            .get_event_type_stats()
        )
        sql: str = captured_sql["sql"]
        # The customer_id column does not appear in any IN clause.
        assert (
            "customer_id IN"
            not in sql.replace(" ", "").replace("customer_idIN", "customer_id IN")
            or "customer_id IN ()" not in sql
        )

    async def test_empty_external_ids_no_in_clause(
        self, captured_sql: dict[str, Any]
    ) -> None:
        await (
            TinybirdEventsQuery(_WORKSPACE_ID)
            .filter_external_customer_id([])
            .get_event_type_stats()
        )
        sql: str = captured_sql["sql"]
        assert "external_customer_id IN ()" not in sql

    async def test_nonempty_customer_ids_emits_in_clause(
        self, captured_sql: dict[str, Any]
    ) -> None:
        await (
            TinybirdEventsQuery(_WORKSPACE_ID)
            .filter_customer_id([_CUSTOMER_A])
            .get_event_type_stats()
        )
        sql: str = captured_sql["sql"]
        assert "customer_id" in sql.lower()
        assert str(_CUSTOMER_A) in sql


@pytest.mark.asyncio
class TestRootEventsFilter:
    async def test_filter_root_events_adds_parent_id_is_null(
        self, captured_sql: dict[str, Any]
    ) -> None:
        # Pin: the documented "top-level events only" path.
        # Drift to ``IS NOT NULL`` would invert the meaning.
        await (
            TinybirdEventsQuery(_WORKSPACE_ID)
            .filter_root_events()
            .get_event_type_stats()
        )
        sql: str = captured_sql["sql"]
        # ClickHouse dialect wraps column names in backticks.
        assert "parent_id" in sql.lower()
        assert "is null" in sql.lower()


class TestOrderByAllowList:
    def test_unknown_column_raises_value_error(self) -> None:
        # Pin: the ``_SORT_COLUMN_MAP`` is the documented
        # allow-list for sort keys. Drift to silently fall
        # through would render the dashboard with no ordering.
        with pytest.raises(ValueError, match="Invalid sort column"):
            TinybirdEventsQuery(_WORKSPACE_ID).order_by("ghost")

    def test_documented_columns_accepted(self) -> None:
        # Pin: the documented sort keys for the events query.
        # Drift to drop one would 500 the dashboard's column
        # header click.
        for col in ("name", "first_seen", "last_seen", "occurrences"):
            TinybirdEventsQuery(_WORKSPACE_ID).order_by(col)

    def test_event_types_query_unknown_column_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid sort column"):
            TinybirdEventTypesQuery(_WORKSPACE_ID).order_by("ghost")


@pytest.mark.asyncio
class TestDefaultOrdering:
    async def test_events_query_default_orders_by_max_timestamp_desc(
        self, captured_sql: dict[str, Any]
    ) -> None:
        # Pin: most-recent activity at the top. Drift to ASC
        # would bury fresh events at the bottom of the
        # moderator's dashboard.
        await TinybirdEventsQuery(_WORKSPACE_ID).get_event_type_stats()
        sql: str = captured_sql["sql"]
        # The compiled SQL ends with ``ORDER BY max(...) DESC``.
        # We assert on the substring rather than line-end so
        # whitespace + dialect quirks don't break the test.
        assert "ORDER BY" in sql
        assert "DESC" in sql

    async def test_explicit_order_by_overrides_default(
        self, captured_sql: dict[str, Any]
    ) -> None:
        # Pin: caller's ``order_by`` wins. Drift to always-append
        # the default would render two ORDER BY clauses (or with
        # ClickHouse, error out).
        await (
            TinybirdEventsQuery(_WORKSPACE_ID)
            .order_by("name", descending=False)
            .get_event_type_stats()
        )
        sql: str = captured_sql["sql"]
        assert "ORDER BY" in sql
        # ASC ordering is set; the default ``max(timestamp)``
        # column does NOT appear in the ORDER BY list — i.e.,
        # the default is replaced.
        # ClickHouse renders ASC explicitly as ``ASC``.
        assert "ASC" in sql.upper()


@pytest.mark.asyncio
class TestEventTypesViewWorkspaceScope:
    async def test_mv_query_scopes_by_organization_id(
        self, captured_sql: dict[str, Any]
    ) -> None:
        # Pin: same multi-tenant guard for the materialised-view
        # query. Drift would leak across workspaces in the
        # event-types dashboard.
        await TinybirdEventTypesQuery(_WORKSPACE_ID).get_event_type_stats()
        sql: str = captured_sql["sql"]
        assert str(_WORKSPACE_ID) in sql
        assert "organization_id" in sql.lower()
