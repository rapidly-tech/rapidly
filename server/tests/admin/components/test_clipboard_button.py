"""Tests for ``rapidly/admin/components/_clipboard_button.py``.

Pin the public export — drift would break every importer.
"""

from __future__ import annotations

from rapidly.admin.components import _clipboard_button as M


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: only ``clipboard_button`` is publicly exported.
        assert M.__all__ == ["clipboard_button"]
