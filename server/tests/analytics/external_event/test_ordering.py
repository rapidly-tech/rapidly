"""Tests for ``rapidly/analytics/external_event/ordering.py``.

Pins the sortable columns on the external-event (inbound webhook)
list endpoint. Enum values are on-wire contract strings; callers
pass ``?sorting=-created_at``.
"""

from __future__ import annotations

from rapidly.analytics.external_event.ordering import ExternalEventSortProperty


class TestExternalEventSortProperty:
    def test_exposes_documented_columns(self) -> None:
        assert {e.value for e in ExternalEventSortProperty} == {
            "source",
            "task_name",
            "created_at",
            "handled_at",
        }

    def test_values_use_snake_case(self) -> None:
        # DB column convention; camelCase would silently break SQL
        # ORDER BY clauses.
        for e in ExternalEventSortProperty:
            assert e.value.islower() or "_" in e.value

    def test_is_str_enum(self) -> None:
        assert str(ExternalEventSortProperty.created_at) == "created_at"
