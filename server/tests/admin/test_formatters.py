"""Tests for ``rapidly/admin/formatters.py``.

Display formatters for admin templates. Three load-bearing surfaces:

- ``datetime`` formats as ``YYYY-MM-DD HH:MM:SS`` — drift would
  silently change every timestamp on every admin page.
- ``currency`` delegates to ``format_currency`` and forwards the
  ``decimal_quantization`` keyword. Drift would either lose the
  cents-rounding control or break locale-aware rendering.
- ``file_size`` uses ``"<n> B"`` for sub-1024 byte values (admin
  convention — no decimal noise on small files) and delegates to
  ``human_readable_size`` for KB+ values. Drift would render
  files like ``800 B`` as ``0.8 KB`` and clutter the UI.
"""

from __future__ import annotations

from datetime import datetime as dt
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from rapidly.admin import formatters as M
from rapidly.admin.formatters import currency, datetime, file_size


class TestDatetime:
    def test_iso_like_format(self) -> None:
        # Pin: YYYY-MM-DD HH:MM:SS — drift would change every
        # timestamp on every admin page.
        assert datetime(dt(2026, 4, 25, 14, 30, 45)) == "2026-04-25 14:30:45"

    def test_zero_padded_components(self) -> None:
        # Pin: zero-padded month / day / hour / minute / second
        # so columns align in DaisyUI tables.
        assert datetime(dt(2026, 1, 5, 9, 7, 3)) == "2026-01-05 09:07:03"

    def test_drops_microseconds(self) -> None:
        # Pin: microseconds are dropped — admin pages don't need
        # sub-second precision and drift would clutter every row.
        assert datetime(dt(2026, 1, 1, 0, 0, 0, 999_999)) == "2026-01-01 00:00:00"


class TestCurrency:
    def test_int_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: integer cents pass through to format_currency. The
        # admin treats integer values as the canonical Stripe
        # cents representation.
        captured: dict[str, object] = {}

        def fake_format_currency(value, code, *, decimal_quantization):  # type: ignore[no-untyped-def]
            captured["value"] = value
            captured["code"] = code
            captured["decimal_quantization"] = decimal_quantization
            return "$10.00"

        monkeypatch.setattr(M, "format_currency", fake_format_currency)

        result = currency(1000, "usd")
        assert result == "$10.00"
        assert captured == {
            "value": 1000,
            "code": "usd",
            "decimal_quantization": True,
        }

    def test_decimal_value_passes_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}
        monkeypatch.setattr(
            M,
            "format_currency",
            lambda value, code, *, decimal_quantization: captured.update(
                {"value": value, "decimal_quantization": decimal_quantization}
            ),
        )
        currency(Decimal("12.34"), "usd")
        assert captured["value"] == Decimal("12.34")

    def test_decimal_quantization_keyword_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: caller-supplied ``decimal_quantization=False`` is
        # forwarded. Used by callers that want to display sub-cent
        # precision (e.g., interim Stripe rate calculations).
        captured: dict[str, object] = {}
        monkeypatch.setattr(
            M,
            "format_currency",
            lambda value, code, *, decimal_quantization: captured.update(
                {"decimal_quantization": decimal_quantization}
            ),
        )
        currency(1, "usd", decimal_quantization=False)
        assert captured["decimal_quantization"] is False

    def test_default_decimal_quantization_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the default is True (round to currency precision).
        captured: dict[str, object] = {}
        monkeypatch.setattr(
            M,
            "format_currency",
            lambda value, code, *, decimal_quantization: captured.update(
                {"decimal_quantization": decimal_quantization}
            ),
        )
        currency(1, "usd")
        assert captured["decimal_quantization"] is True


class TestFileSize:
    def test_sub_1024_uses_b_unit(self) -> None:
        # Pin: bytes-only formatting for small files (no decimal
        # noise like 0.5 KB on a 500-byte file).
        assert file_size(0) == "0 B"
        assert file_size(1) == "1 B"
        assert file_size(1023) == "1023 B"

    def test_at_1024_delegates_to_human_readable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: at exactly 1024 bytes we delegate to
        # ``human_readable_size`` (yields KB / MB / GB / TB
        # with 1-decimal precision per util convention).
        sentinel = MagicMock()
        captured: dict[str, int] = {}

        def fake(size: int) -> object:
            captured["size"] = size
            return sentinel

        monkeypatch.setattr(M, "human_readable_size", fake)
        result = file_size(1024)
        assert result is sentinel
        assert captured["size"] == 1024

    def test_large_value_delegates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sentinel = MagicMock()
        monkeypatch.setattr(M, "human_readable_size", lambda size: sentinel)
        assert file_size(10 * 1024 * 1024) is sentinel
