"""Tests for ``rapidly/analytics/event_type/ordering.py``.

Pins the sortable columns on the event-type aggregation list
endpoint. ``event_type_name`` / ``event_type_label`` are Python
attribute aliases (``name`` / ``label`` are awkward on StrEnum); the
on-wire values stay as ``name`` + ``label``.
"""

from __future__ import annotations

from rapidly.analytics.event_type.ordering import EventTypesSortProperty


class TestEventTypesSortProperty:
    def test_exposes_documented_columns(self) -> None:
        assert {e.value for e in EventTypesSortProperty} == {
            "name",
            "label",
            "occurrences",
            "first_seen",
            "last_seen",
        }

    def test_name_attribute_alias(self) -> None:
        # ``event_type_name`` attribute → ``"name"`` on-wire. Pinned
        # so a refactor to ``name`` attribute (illegal for StrEnum
        # class var resolution) or to ``"event_type_name"`` on-wire
        # (breaks saved sort params) is caught.
        assert EventTypesSortProperty.event_type_name.value == "name"

    def test_label_attribute_alias(self) -> None:
        assert EventTypesSortProperty.event_type_label.value == "label"

    def test_is_str_enum(self) -> None:
        assert str(EventTypesSortProperty.last_seen) == "last_seen"
