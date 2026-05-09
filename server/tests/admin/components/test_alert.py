"""Tests for ``rapidly/admin/components/_alert.py``.

DaisyUI alert component variant map. Two load-bearing surfaces:

- ``_VARIANT_CLASS`` maps the four toast / alert levels to
  DaisyUI's ``alert-*`` colour classes. The toast layer reads
  these literals when rendering server-pushed notifications;
  drift would silently change every alert / toast colour.
- ``__all__`` exports ``Variant`` (the Literal type) — callers
  that type-hint with this name (``add_toast(... variant: Variant)``)
  rely on the export being stable.
"""

from __future__ import annotations

from rapidly.admin.components import _alert as M
from rapidly.admin.components._alert import _VARIANT_CLASS


class TestVariantClass:
    def test_four_documented_variants(self) -> None:
        # Pin: info / success / warning / error — the documented
        # alert levels. Drift to drop one would crash the
        # renderer when a caller requests it.
        assert set(_VARIANT_CLASS.keys()) == {
            "info",
            "success",
            "warning",
            "error",
        }

    def test_class_format(self) -> None:
        # Pin: ``alert-<variant>`` per DaisyUI. Drift would emit
        # non-existent classes.
        assert _VARIANT_CLASS == {
            "info": "alert-info",
            "success": "alert-success",
            "warning": "alert-warning",
            "error": "alert-error",
        }


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: ``Variant`` Literal type is the only public export.
        assert M.__all__ == ["Variant"]
