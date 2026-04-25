"""Tests for ``rapidly/admin/components/_modal.py``.

Pin the public export.
"""

from __future__ import annotations

from rapidly.admin.components import _modal as M


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        assert M.__all__ == ["modal"]
