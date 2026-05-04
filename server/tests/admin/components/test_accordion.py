"""Tests for ``rapidly/admin/components/_accordion.py``.

Pin the public export.
"""

from __future__ import annotations

from rapidly.admin.components import _accordion as M


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: only ``item`` is publicly exported (the
        # accordion-item context manager).
        assert M.__all__ == ["item"]
