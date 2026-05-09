"""Tests for ``rapidly/admin/components/_button.py``.

DaisyUI button component variant/size class maps. Two load-bearing
surfaces:

- ``_VARIANT_CLASS`` covers all 8 documented colour variants
  (neutral / primary / secondary / accent / info / success /
  warning / error). Drift to drop one would crash the renderer
  with KeyError when a caller requests it.
- ``_SIZE_CLASS`` covers all 5 sizes (xs / sm / md / lg / xl).
  Drift to drop one would crash the renderer.
"""

from __future__ import annotations

from rapidly.admin.components import _button as M
from rapidly.admin.components._button import (
    _SIZE_CLASS,
    _VARIANT_CLASS,
)


class TestVariantClass:
    def test_all_eight_variants_present(self) -> None:
        # Pin: 8 documented colour variants.
        assert set(_VARIANT_CLASS.keys()) == {
            "neutral",
            "primary",
            "secondary",
            "accent",
            "info",
            "success",
            "warning",
            "error",
        }

    def test_class_format_is_btn_dash_variant(self) -> None:
        # Pin: class format ``btn-<variant>`` matches DaisyUI
        # convention. Drift would emit non-existent classes.
        for variant, css in _VARIANT_CLASS.items():
            assert css == f"btn-{variant}"


class TestSizeClass:
    def test_all_five_sizes_present(self) -> None:
        # Pin: five DaisyUI sizes.
        assert set(_SIZE_CLASS.keys()) == {"xs", "sm", "md", "lg", "xl"}

    def test_class_format_is_btn_dash_size(self) -> None:
        # Pin: class format ``btn-<size>`` matches DaisyUI.
        for size, css in _SIZE_CLASS.items():
            assert css == f"btn-{size}"


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: only ``button`` is publicly exported.
        assert M.__all__ == ["button"]
