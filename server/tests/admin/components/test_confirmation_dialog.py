"""Tests for ``rapidly/admin/components/_confirmation_dialog.py``.

Confirmation dialog variants. Two load-bearing surfaces:

- ``_VARIANT_SPECS`` covers the four documented variants
  (info / success / warning / error), each carrying both an
  emoji icon and a button-variant. Drift to drop one would let
  the renderer fall back to ``warning`` silently.
- The mapping pairs each Variant with the matching button
  ButtonVariant — drift would render a destructive action with
  a non-matching button colour (e.g., red message + green
  button is confusing).
"""

from __future__ import annotations

from rapidly.admin.components import _confirmation_dialog as M
from rapidly.admin.components._confirmation_dialog import _VARIANT_SPECS


class TestVariantSpecs:
    def test_four_documented_variants(self) -> None:
        # Pin: info / success / warning / error.
        assert set(_VARIANT_SPECS.keys()) == {
            "info",
            "success",
            "warning",
            "error",
        }

    def test_each_spec_has_icon_and_button(self) -> None:
        # Pin: every spec carries both an icon string and a
        # button variant. Drift to drop a key would crash on
        # render with KeyError.
        for spec in _VARIANT_SPECS.values():
            assert "icon" in spec
            assert "button" in spec

    def test_button_variant_matches_dialog_variant(self) -> None:
        # Pin: confirm button colour matches the dialog colour.
        # Drift to mismatched (e.g., red dialog + green button)
        # would confuse users on destructive actions.
        for variant_name, spec in _VARIANT_SPECS.items():
            assert spec["button"] == variant_name

    def test_icons_are_unicode_emoji(self) -> None:
        # Pin: emoji glyphs (NOT ASCII or text). Drift would
        # break visual scan-ability of confirmation dialogs.
        # ℹ✅⚠❌ all carry visual-glyph code points.
        assert _VARIANT_SPECS["info"]["icon"] == "\u2139\ufe0f"
        assert _VARIANT_SPECS["success"]["icon"] == "\u2705"
        assert _VARIANT_SPECS["warning"]["icon"] == "\u26a0\ufe0f"
        assert _VARIANT_SPECS["error"]["icon"] == "\u274c"


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        assert M.__all__ == ["Variant", "confirmation_dialog"]
