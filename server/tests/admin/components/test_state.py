"""Tests for ``rapidly/admin/components/_state.py``.

Pin the spinner-size mapping + public exports.

- ``_SPINNER_SIZES`` maps short names (xs / sm / md / lg) to
  DaisyUI ``loading-*`` classes. Drift would render the wrong
  spinner size and clutter / hide the loading affordance on
  long-running admin operations.
- ``__all__`` exposes ``card`` / ``empty_state`` / ``loading_state``
  — drift would break every importer.
"""

from __future__ import annotations

from rapidly.admin.components import _state as M
from rapidly.admin.components._state import _SPINNER_SIZES


class TestSpinnerSizes:
    def test_four_documented_sizes(self) -> None:
        # Pin: xs / sm / md / lg — the documented size set.
        # Drift to add a 5th size without updating templates
        # would render an inconsistent loading affordance.
        assert set(_SPINNER_SIZES.keys()) == {"xs", "sm", "md", "lg"}

    def test_class_names_pinned(self) -> None:
        # Pin: DaisyUI class names per size. Drift would render
        # the wrong spinner size on every loading state.
        assert _SPINNER_SIZES == {
            "xs": "loading-xs",
            "sm": "loading-sm",
            "md": "loading-md",
            "lg": "loading-lg",
        }


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: the public exports.
        assert M.__all__ == ["card", "empty_state", "loading_state"]
