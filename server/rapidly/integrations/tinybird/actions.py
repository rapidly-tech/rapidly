"""Tinybird integration for high-volume event analytics.

Bridges the Rapidly event model with Tinybird's ClickHouse-backed
analytics engine.  Handles event ingestion (NDJSON push), time-series
queries, and customer-scoped event listing with transparent fallback
to PostgreSQL when Tinybird is not configured.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any, Self
from uuid import UUID

import structlog
from clickhouse_connect.cc_sqlalchemy.dialect import ClickHouseDialect
from sqlalchemy import Column, DateTime, MetaData, String, Table, func, select
from sqlalchemy.sql import Select

from rapidly.config import settings
from rapidly.logging import Logger
from rapidly.models import Event
from rapidly.models.event import EventSource

from .client import client
from .types import TinybirdEvent

_log: Logger = structlog.get_logger()

clickhouse_dialect = ClickHouseDialect()
metadata = MetaData()

events_table = Table(
    "events_by_ingested_at",
    metadata,
    Column("name", String),
    Column("source", String),
    Column("organization_id", String),
    Column("customer_id", String),
    Column("external_customer_id", String),
    Column("parent_id", String),
    Column("timestamp", DateTime),
)

event_types_mv = Table(
    "event_types",
    metadata,
    Column("name", String),
    Column("source", String),
    Column("organization_id", String),
    Column("occurrences", String),
    Column("first_seen", DateTime),
    Column("last_seen", DateTime),
)


@dataclass
class TinybirdEventTypeStats:
    name: str
    source: EventSource
    occurrences: int
    first_seen: datetime
    last_seen: datetime


DATASOURCE_EVENTS = "events_by_ingested_at"


# ── Ingestion ──


def _pop_system_metadata(m: dict[str, Any], is_system: bool, key: str) -> Any:
    v = m.pop(key, None) if is_system else None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _event_to_tinybird(event: Event) -> TinybirdEvent:
    m = dict(event.user_metadata or {})
    cost = m.pop("_cost", None) or {}
    llm = m.pop("_llm", None) or {}

    is_system = event.source == EventSource.system
    pop = partial(_pop_system_metadata, m, is_system)

    return TinybirdEvent(
        id=str(event.id),
        ingested_at=event.ingested_at.isoformat(),
        timestamp=event.timestamp.isoformat(),
        name=event.name,
        source=event.source,
        organization_id=str(event.workspace_id),
        customer_id=str(event.customer_id) if event.customer_id else None,
        external_customer_id=event.external_customer_id,
        member_id=str(event.member_id) if event.member_id else None,
        external_member_id=event.external_member_id,
        external_id=event.external_id,
        parent_id=str(event.parent_id) if event.parent_id else None,
        root_id=str(event.root_id) if event.root_id else None,
        event_type_id=str(event.event_type_id) if event.event_type_id else None,
        meter_id=pop("meter_id"),
        units=pop("units"),
        rollover=pop("rollover"),
        share_id=pop("share_id"),
        transaction_id=pop("transaction_id"),
        amount=pop("amount"),
        currency=pop("currency"),
        customer_email=pop("customer_email"),
        customer_name=pop("customer_name"),
        cost_amount=cost.get("amount"),
        cost_currency=cost.get("currency"),
        llm_vendor=llm.get("vendor"),
        llm_model=llm.get("model"),
        llm_input_tokens=llm.get("input_tokens"),
        llm_output_tokens=llm.get("output_tokens"),
        user_metadata=json.dumps(m) if m else "{}",
    )


async def ingest_events(events: Sequence[Event]) -> None:
    if not settings.TINYBIRD_EVENTS_WRITE:
        return

    if not events:
        return

    try:
        tinybird_events = [_event_to_tinybird(e) for e in events]
        await client.ingest(DATASOURCE_EVENTS, tinybird_events)
    except Exception as e:
        _log.error(
            "tinybird.ingest_events.failed", error=str(e), event_count=len(events)
        )


# ── Query Builders ──


def _compile(statement: Select[Any]) -> tuple[str, str]:
    compiled = statement.compile(dialect=clickhouse_dialect)
    template = str(compiled)
    literal = str(
        statement.compile(
            dialect=clickhouse_dialect, compile_kwargs={"literal_binds": True}
        )
    )
    return literal, template


# ── Stats ──


def _parse_event_type_stats(rows: list[dict[str, Any]]) -> list[TinybirdEventTypeStats]:
    return [
        TinybirdEventTypeStats(
            name=row["name"],
            source=EventSource(row["source"]),
            occurrences=row["occurrences"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
        )
        for row in rows
    ]


class TinybirdEventsQuery:
    """
    Query builder for the raw events table.

    Supports all filters including customer_id, external_customer_id,
    parent_id, root_events, and source.
    """

    def __init__(self, workspace_id: UUID) -> None:
        self._workspace_id = str(workspace_id)
        self._filters: list[Any] = []
        self._order_by_clauses: list[Any] = []

    def filter_customer_id(self, customer_ids: Sequence[UUID]) -> Self:
        if customer_ids:
            self._filters.append(
                events_table.c.customer_id.in_([str(c) for c in customer_ids])
            )
        return self

    def filter_external_customer_id(self, external_ids: Sequence[str]) -> Self:
        if external_ids:
            self._filters.append(
                events_table.c.external_customer_id.in_(list(external_ids))
            )
        return self

    def filter_root_events(self) -> Self:
        self._filters.append(events_table.c.parent_id.is_(None))
        return self

    def filter_parent_id(self, parent_id: UUID) -> Self:
        self._filters.append(events_table.c.parent_id == str(parent_id))
        return self

    def filter_source(self, source: EventSource) -> Self:
        self._filters.append(events_table.c.source == source.value)
        return self

    _SORT_COLUMN_MAP = {
        "name": events_table.c.name,
        "first_seen": func.min(events_table.c.timestamp),
        "last_seen": func.max(events_table.c.timestamp),
        "occurrences": func.count(),
    }

    def order_by(self, column: str, descending: bool = False) -> Self:
        col = self._SORT_COLUMN_MAP.get(column)
        if col is None:
            raise ValueError(f"Invalid sort column: {column}")
        self._order_by_clauses.append(col.desc() if descending else col.asc())
        return self

    async def get_event_type_stats(self) -> list[TinybirdEventTypeStats]:
        statement = (
            select(
                events_table.c.name,
                events_table.c.source,
                func.count().label("occurrences"),
                func.min(events_table.c.timestamp).label("first_seen"),
                func.max(events_table.c.timestamp).label("last_seen"),
            )
            .where(events_table.c.organization_id == self._workspace_id)
            .group_by(events_table.c.name, events_table.c.source)
        )

        for f in self._filters:
            statement = statement.where(f)

        if self._order_by_clauses:
            statement = statement.order_by(*self._order_by_clauses)
        else:
            statement = statement.order_by(func.max(events_table.c.timestamp).desc())

        sql, template = _compile(statement)

        try:
            rows = await client.query(sql, db_statement=template)
            return _parse_event_type_stats(rows)
        except Exception as e:
            _log.error("tinybird.get_event_type_stats.failed", error=str(e))
            raise


class TinybirdEventTypesQuery:
    """
    Query builder for the event_types materialized view.

    Supports source filter only. For customer/parent filtering,
    use TinybirdEventsQuery against the raw table.
    """

    def __init__(self, workspace_id: UUID) -> None:
        self._workspace_id = str(workspace_id)
        self._filters: list[Any] = []
        self._order_by_clauses: list[Any] = []

    def filter_source(self, source: EventSource) -> Self:
        self._filters.append(event_types_mv.c.source == source.value)
        return self

    _SORT_COLUMN_MAP = {
        "name": event_types_mv.c.name,
        "first_seen": func.minMerge(event_types_mv.c.first_seen),
        "last_seen": func.maxMerge(event_types_mv.c.last_seen),
        "occurrences": func.countMerge(event_types_mv.c.occurrences),
    }

    def order_by(self, column: str, descending: bool = False) -> Self:
        col = self._SORT_COLUMN_MAP.get(column)
        if col is None:
            raise ValueError(f"Invalid sort column: {column}")
        self._order_by_clauses.append(col.desc() if descending else col.asc())
        return self

    async def get_event_type_stats(self) -> list[TinybirdEventTypeStats]:
        statement = (
            select(
                event_types_mv.c.name,
                event_types_mv.c.source,
                func.countMerge(event_types_mv.c.occurrences).label("occurrences"),
                func.minMerge(event_types_mv.c.first_seen).label("first_seen"),
                func.maxMerge(event_types_mv.c.last_seen).label("last_seen"),
            )
            .where(event_types_mv.c.organization_id == self._workspace_id)
            .group_by(event_types_mv.c.name, event_types_mv.c.source)
        )

        for f in self._filters:
            statement = statement.where(f)

        if self._order_by_clauses:
            statement = statement.order_by(*self._order_by_clauses)
        else:
            statement = statement.order_by(
                func.maxMerge(event_types_mv.c.last_seen).desc()
            )

        sql, template = _compile(statement)

        try:
            rows = await client.query(sql, db_statement=template)
            return _parse_event_type_stats(rows)
        except Exception as e:
            _log.error("tinybird.get_event_type_stats_from_mv.failed", error=str(e))
            raise
