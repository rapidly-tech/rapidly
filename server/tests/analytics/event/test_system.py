"""Tests for ``rapidly/analytics/event/system.py`` — system event
catalogue.

Pins the ``SystemEvent`` enum (the wire names external consumers
subscribe to) and the ``SYSTEM_EVENT_LABELS`` display map. A renamed
event silently breaks every webhook subscription; a missing label
renders as the raw machine name in the dashboard UI.
"""

from __future__ import annotations

from rapidly.analytics.event.system import (
    SYSTEM_EVENT_LABELS,
    SystemEvent,
)


class TestSystemEventEnum:
    def test_contains_customer_lifecycle_events(self) -> None:
        # ``customer.created``, ``customer.updated``, ``customer.deleted``
        # — the three lifecycle events subscribers currently key on.
        assert {e.value for e in SystemEvent} == {
            "customer.created",
            "customer.updated",
            "customer.deleted",
        }

    def test_uses_dotted_namespace_convention(self) -> None:
        # Every event name follows ``<resource>.<action>`` — pinned so
        # an accidental ``customer_created`` (underscore) rename would
        # fail loudly instead of silently breaking webhook filters that
        # key on the dotted form.
        for e in SystemEvent:
            assert "." in e.value
            parts = e.value.split(".")
            assert len(parts) == 2
            assert all(parts)

    def test_is_a_str_enum(self) -> None:
        # StrEnum — direct string comparison in SQL and JSON.
        assert str(SystemEvent.customer_created) == "customer.created"


class TestSystemEventLabels:
    def test_has_label_for_every_event(self) -> None:
        # Missing label → dashboard UI renders ``customer.created``
        # instead of ``Customer Created``. Drift catch: adding a new
        # SystemEvent without updating the label map would be caught.
        missing = {e.value for e in SystemEvent} - set(SYSTEM_EVENT_LABELS.keys())
        assert missing == set(), f"events without labels: {missing}"

    def test_labels_are_non_empty_human_readable_strings(self) -> None:
        for name, label in SYSTEM_EVENT_LABELS.items():
            assert label, f"empty label for {name}"
            # Title-case heuristic: first char uppercase.
            assert label[0].isupper(), f"non-title-case label for {name}: {label}"

    def test_customer_event_labels_follow_subject_verb_convention(self) -> None:
        # "Customer Created", "Customer Updated", "Customer Deleted" —
        # pinned so a refactor to "Created Customer" (verb-subject)
        # would require an explicit i18n review.
        assert SYSTEM_EVENT_LABELS["customer.created"] == "Customer Created"
        assert SYSTEM_EVENT_LABELS["customer.updated"] == "Customer Updated"
        assert SYSTEM_EVENT_LABELS["customer.deleted"] == "Customer Deleted"

    def test_label_keys_match_event_values_exactly(self) -> None:
        # No stray entries in the map that don't correspond to a
        # SystemEvent.
        extra = set(SYSTEM_EVENT_LABELS.keys()) - {e.value for e in SystemEvent}
        assert extra == set(), f"orphan labels: {extra}"
