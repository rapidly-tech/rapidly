"""Tests for ``rapidly/analytics/event_type/types.py`` —
``EventTypeUpdate`` mutation validators + read-model shape.

The ``label`` + ``label_property_selector`` validators trim whitespace
before storage. Without the strip step a user could submit a label of
``"   "`` that renders as empty in the UI but passes the non-empty
check, or a label with leading/trailing whitespace that breaks string
matching in downstream analytics queries.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rapidly.analytics.event_type.types import (
    EventType,
    EventTypeUpdate,
    EventTypeWithStats,
)
from rapidly.models.event import EventSource


class TestEventTypeUpdateLabelValidator:
    def test_strips_whitespace_from_valid_label(self) -> None:
        u = EventTypeUpdate(label="  customer created  ")
        assert u.label == "customer created"

    def test_rejects_empty_after_strip(self) -> None:
        # All-whitespace would pass min_length=1 on the raw input
        # (length of "   " is 3), but the validator explicitly rejects
        # cleaned empty strings. Pin the guard.
        with pytest.raises(ValidationError, match="Label cannot be empty"):
            EventTypeUpdate(label="   ")

    def test_rejects_empty_string_via_min_length(self) -> None:
        with pytest.raises(ValidationError):
            EventTypeUpdate(label="")

    def test_rejects_label_over_128_chars(self) -> None:
        with pytest.raises(ValidationError):
            EventTypeUpdate(label="a" * 129)

    def test_allows_label_at_128_chars(self) -> None:
        u = EventTypeUpdate(label="a" * 128)
        assert len(u.label or "") == 128

    def test_label_can_be_omitted(self) -> None:
        # label is Optional — the update can target only
        # label_property_selector.
        u = EventTypeUpdate(label_property_selector="subject")
        assert u.label is None


class TestEventTypeUpdateLabelPropertySelector:
    def test_strips_whitespace(self) -> None:
        u = EventTypeUpdate(label_property_selector="  metadata.subject  ")
        assert u.label_property_selector == "metadata.subject"

    def test_normalises_all_whitespace_to_none(self) -> None:
        # Unlike ``label``, the selector validator doesn't raise — it
        # collapses empty-after-strip to None so callers can clear it.
        u = EventTypeUpdate(label="x", label_property_selector="   ")
        assert u.label_property_selector is None

    def test_rejects_over_256_chars(self) -> None:
        with pytest.raises(ValidationError):
            EventTypeUpdate(label_property_selector="a" * 257)

    def test_allows_selector_at_256_chars(self) -> None:
        u = EventTypeUpdate(label_property_selector="a" * 256)
        assert len(u.label_property_selector or "") == 256

    def test_can_be_omitted(self) -> None:
        u = EventTypeUpdate(label="customer created")
        assert u.label_property_selector is None


class TestEventTypeReadModel:
    def test_required_fields_round_trip(self) -> None:
        event_id = uuid.uuid4()
        org_id = uuid.uuid4()
        now = datetime(2026, 4, 23, tzinfo=UTC)
        et = EventType(
            id=event_id,
            created_at=now,
            modified_at=None,
            name="customer.created",
            label="Customer Created",
            label_property_selector=None,
            workspace_id=org_id,
        )
        assert et.id == event_id
        assert et.name == "customer.created"
        assert et.label == "Customer Created"
        assert et.label_property_selector is None
        assert et.workspace_id == org_id


class TestEventTypeWithStats:
    def test_extends_EventType_with_stats_fields(self) -> None:
        et = EventTypeWithStats(
            id=uuid.uuid4(),
            created_at=datetime(2026, 4, 23, tzinfo=UTC),
            modified_at=None,
            name="customer.created",
            label="Customer Created",
            label_property_selector=None,
            workspace_id=uuid.uuid4(),
            source=EventSource.system,
            occurrences=42,
            first_seen=datetime(2026, 1, 1, tzinfo=UTC),
            last_seen=datetime(2026, 4, 23, tzinfo=UTC),
        )
        assert et.source == EventSource.system
        assert et.occurrences == 42
        assert et.first_seen < et.last_seen

    def test_is_subclass_of_EventType(self) -> None:
        # The stats envelope adds fields; it must NOT diverge into a
        # separate type tree — list endpoints use ``EventTypeWithStats``
        # where the detail endpoint returns ``EventType``, and they're
        # supposed to share the same core shape.
        assert issubclass(EventTypeWithStats, EventType)
