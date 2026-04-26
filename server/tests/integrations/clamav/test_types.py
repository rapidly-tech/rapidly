"""Tests for ``rapidly/integrations/clamav/types.py``.

ClamAV scan-status enum. Two load-bearing surfaces:

- ``ScanStatus`` is a ``StrEnum`` so the wire-format value (e.g.
  ``"clean"``) round-trips through Pydantic / JSON / Postgres
  without an explicit serialiser. Drift to plain ``Enum`` would
  break every external integration that consumes the status.
- The exact six member set is the documented contract for the AV
  pipeline state machine (pending → scanning → terminal). Adding
  or renaming a state silently changes downstream filter / alert
  rules.
"""

from __future__ import annotations

from enum import StrEnum

from rapidly.integrations.clamav.types import ScanStatus


class TestScanStatusEnum:
    def test_is_string_enum(self) -> None:
        # Wire-format compatibility — drift to plain Enum breaks
        # every consumer that compares against the bare string.
        assert issubclass(ScanStatus, StrEnum)

    def test_member_set_pinned(self) -> None:
        # The exact state machine. Drift here changes filter
        # semantics in dashboards + notification rules.
        assert {s.value for s in ScanStatus} == {
            "pending",
            "scanning",
            "clean",
            "infected",
            "error",
            "skipped",
        }

    def test_values_match_attribute_names(self) -> None:
        # Pin: the attribute name and wire value are identical so
        # callers can use either form interchangeably without
        # a translation layer.
        for s in ScanStatus:
            assert s.name == s.value

    def test_string_equality_with_wire_value(self) -> None:
        # StrEnum: ``ScanStatus.clean == "clean"`` is True. Pinning
        # this prevents a regression to an Enum subclass that
        # silently broke direct string comparisons in queries.
        assert ScanStatus.clean == "clean"
        assert ScanStatus.infected == "infected"

    def test_terminal_states_are_documented(self) -> None:
        # The pipeline contract: the AV worker writes one of these
        # three terminal values after scanning completes. Drift
        # here would let the sweep job re-process completed scans.
        terminal = {
            ScanStatus.clean,
            ScanStatus.infected,
            ScanStatus.error,
            ScanStatus.skipped,
        }
        assert {s.value for s in terminal} == {"clean", "infected", "error", "skipped"}
