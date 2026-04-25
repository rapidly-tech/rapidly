"""Tests for ``rapidly/admin/components/_metric_card.py``.

Two load-bearing surfaces:

- ``_TREND_SYMBOLS`` — Unicode arrow glyphs for up / down /
  neutral. Drift to ASCII would break visual scanning of
  dashboards (admins rely on the arrow direction at a glance).
- ``_TREND_COLORS`` — every trend has a class. Drift to drop one
  would crash the renderer with KeyError when a caller passes
  that trend.
"""

from __future__ import annotations

from rapidly.admin.components import _metric_card as M
from rapidly.admin.components._metric_card import (
    _TREND_COLORS,
    _TREND_SYMBOLS,
)


class TestTrendSymbols:
    def test_three_directions(self) -> None:
        # Pin: up / down / neutral are the documented directions.
        assert set(_TREND_SYMBOLS.keys()) == {"up", "down", "neutral"}

    def test_uses_unicode_arrows(self) -> None:
        # Pin: Unicode arrow glyphs (NOT ASCII >, <, =). Drift
        # would break visual scanning at a glance.
        assert _TREND_SYMBOLS["up"] == "\u2197"  # north-east arrow
        assert _TREND_SYMBOLS["down"] == "\u2198"  # south-east arrow
        assert _TREND_SYMBOLS["neutral"] == "\u2192"  # right arrow


class TestTrendColors:
    def test_three_directions(self) -> None:
        # Pin: every trend has a class entry. Drift would crash
        # with KeyError when the caller renders a trend without
        # a colour.
        assert set(_TREND_COLORS.keys()) == {"up", "down", "neutral"}

    def test_class_format_uses_text_base_content(self) -> None:
        # Pin: trend colours use the muted base-content scale
        # (NOT semantic green/red). Drift to red/green would
        # over-emphasise the trend visually and clash with the
        # rest of the admin's neutral palette.
        for cls in _TREND_COLORS.values():
            assert cls.startswith("text-base-content")


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        assert M.__all__ == ["Variant", "metric_card"]
