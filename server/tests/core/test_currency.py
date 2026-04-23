"""Tests for ``rapidly/core/currency.py``.

Pins the ``PresentmentCurrency`` enum membership (contract for the
storefront + billing) and the ``format_currency`` smallest-unit →
localised display transform. Assertions focus on structural properties
(symbol present, decimal handling) rather than exact locale strings so
Babel / CLDR updates don't flap the suite.
"""

from __future__ import annotations

from decimal import Decimal

from rapidly.core.currency import PresentmentCurrency, format_currency


class TestPresentmentCurrency:
    def test_contains_the_documented_currencies(self) -> None:
        expected = {
            "aud",
            "brl",
            "cad",
            "chf",
            "eur",
            "inr",
            "gbp",
            "jpy",
            "sek",
            "usd",
        }
        assert {c.value for c in PresentmentCurrency} == expected

    def test_members_are_lowercase_codes(self) -> None:
        # Lowercase is the storage convention across the app (Stripe's
        # API accepts either, but our DB and URLs use lowercase).
        for c in PresentmentCurrency:
            assert c.value == c.value.lower()

    def test_is_a_str_enum(self) -> None:
        # StrEnum members are directly comparable with plain strings —
        # important for SQL queries that pass string currency codes.
        assert PresentmentCurrency.usd == "usd"

    def test_exactly_ten_currencies(self) -> None:
        # Pinning the count guards against accidental additions/removals
        # that would require a corresponding update to
        # ``_CURRENCY_DECIMAL_FACTORS`` — they must stay in sync.
        assert len(list(PresentmentCurrency)) == 10


class TestFormatCurrency:
    def test_formats_500_cents_as_5_usd_with_dollar_sign(self) -> None:
        out = format_currency(500, "usd")
        assert "$" in out
        assert "5" in out

    def test_handles_zero(self) -> None:
        out = format_currency(0, "usd")
        assert "0" in out

    def test_negative_values_render_with_a_sign(self) -> None:
        out = format_currency(-500, "usd")
        # Either a leading "-" or parentheses depending on locale, but
        # the dollar sign must still be there.
        assert "$" in out
        assert "-" in out or "(" in out

    def test_accepts_Decimal_amounts(self) -> None:
        # Accepted per the type signature — prevents an accidental
        # refactor that'd drop Decimal support (which the billing layer
        # relies on for high-precision amounts).
        out = format_currency(Decimal("12345"), "usd")
        assert "$" in out

    def test_accepts_float_amounts(self) -> None:
        out = format_currency(12345.0, "usd")
        assert "$" in out

    def test_JPY_has_no_decimal_fraction(self) -> None:
        # decimal factor = 1 for JPY (zero-cent currency). 1000 value
        # = ¥1,000 — no decimal point.
        out = format_currency(1000, "jpy")
        assert "1,000" in out
        assert "." not in out

    def test_EUR_uses_euro_symbol(self) -> None:
        out = format_currency(500, "eur")
        # Babel renders EUR as "€5.00" in en_US locale.
        assert "€" in out or "EUR" in out

    def test_GBP_uses_pound_symbol(self) -> None:
        out = format_currency(500, "gbp")
        assert "£" in out or "GBP" in out

    def test_accepts_PresentmentCurrency_enum_value(self) -> None:
        # Both enum member and string should work (StrEnum interops).
        via_enum = format_currency(500, PresentmentCurrency.usd)
        via_str = format_currency(500, "usd")
        assert via_enum == via_str

    def test_cents_to_major_unit_conversion(self) -> None:
        # 12345 cents USD = $123.45 (decimal factor 100).
        # Pinning the numeric value (not the exact format) prevents a
        # refactor that drops the "divide by decimal factor" step.
        out = format_currency(12345, "usd")
        assert "123" in out
        assert "45" in out
