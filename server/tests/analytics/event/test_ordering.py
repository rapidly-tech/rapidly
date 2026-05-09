"""Tests for ``rapidly/analytics/event/ordering.py`` — sort-column
enums + default-sort pinning for the event list endpoints.

The enum values are on-wire contract strings: callers pass
``?sorting=-last_seen`` etc. A silent rename (``last_seen`` → ``lastSeen``)
would break every saved dashboard filter.
"""

from __future__ import annotations

from rapidly.analytics.event.ordering import (
    EventNamesSortProperty,
    EventSortProperty,
    EventStatisticsSortProperty,
)


class TestEventSortProperty:
    def test_contains_only_timestamp(self) -> None:
        # Raw event list only sorts by timestamp — pinned so adding a
        # new column requires conscious API-change review.
        assert {e.value for e in EventSortProperty} == {"timestamp"}


class TestEventNamesSortProperty:
    def test_exposes_documented_aggregation_columns(self) -> None:
        assert {e.value for e in EventNamesSortProperty} == {
            "last_seen",
            "first_seen",
            "occurrences",
            "name",
        }

    def test_event_name_attribute_wires_to_name_string(self) -> None:
        # The Python attribute is ``event_name`` (because ``name`` is
        # a reserved word on StrEnum), but the on-wire value is
        # ``name``. Pinned so the enum stays aligned with the DB
        # column and external callers' sorting params.
        assert EventNamesSortProperty.event_name.value == "name"


class TestEventStatisticsSortProperty:
    def test_exposes_documented_statistical_columns(self) -> None:
        assert {e.value for e in EventStatisticsSortProperty} == {
            "total",
            "occurrences",
            "average",
            "p95",
            "p99",
            "name",
        }

    def test_event_name_attribute_wires_to_name_string(self) -> None:
        # Same alias pattern as EventNamesSortProperty — the Python
        # attribute ``event_name`` maps to the wire string ``name``.
        assert EventStatisticsSortProperty.event_name.value == "name"

    def test_includes_both_p95_and_p99_percentiles(self) -> None:
        # Percentile columns are a common source of refactor-breakage
        # (p95/p99 typo'd as P95/P99). Pinned lowercase.
        assert EventStatisticsSortProperty.p95.value == "p95"
        assert EventStatisticsSortProperty.p99.value == "p99"


class TestEnumsAreStrEnumCompatible:
    def test_members_compare_as_strings(self) -> None:
        # StrEnum — pinning so a refactor to plain ``Enum`` breaks the
        # frontend comparisons that do ``sort.value === "timestamp"``.
        assert str(EventSortProperty.timestamp) == "timestamp"
        assert str(EventNamesSortProperty.last_seen) == "last_seen"
        assert str(EventStatisticsSortProperty.total) == "total"
