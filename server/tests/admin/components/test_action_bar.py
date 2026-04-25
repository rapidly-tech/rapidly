"""Tests for ``rapidly/admin/components/_action_bar.py``.

Action-bar layout constants. Two load-bearing surfaces:

- ``_JUSTIFY_MAP`` covers the four documented positions
  (left / center / right / between) with Tailwind ``justify-*``
  classes. Drift to drop one would crash the renderer with
  KeyError when a caller passes that position.
- ``__all__`` exports ``Position`` (Literal type) + ``action_bar``
  (context manager) — drift would break every importer.
"""

from __future__ import annotations

from rapidly.admin.components import _action_bar as M
from rapidly.admin.components._action_bar import _JUSTIFY_MAP


class TestJustifyMap:
    def test_four_documented_positions(self) -> None:
        # Pin: the documented Position Literal values map 1:1 to
        # _JUSTIFY_MAP keys. Drift to add a 5th position without
        # updating the map would crash on render.
        assert set(_JUSTIFY_MAP.keys()) == {
            "left",
            "center",
            "right",
            "between",
        }

    def test_class_names_use_tailwind_justify(self) -> None:
        # Pin: Tailwind ``justify-*`` classes. Drift to non-Tailwind
        # names would silently render with no flex justification.
        assert _JUSTIFY_MAP == {
            "left": "justify-start",
            "center": "justify-center",
            "right": "justify-end",
            "between": "justify-between",
        }


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        assert M.__all__ == ["Position", "action_bar"]
