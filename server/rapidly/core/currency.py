"""Currency helpers: formatting, conversion, and the presentment-currency enum.

Provides ``PresentmentCurrency`` (the set of currencies the platform
supports for display), cent↔decimal conversion, and locale-aware
currency formatting via Babel.
"""

from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from babel.numbers import format_currency as _format_currency

from rapidly.config import settings

# ── Presentment Currency Enum ──

if TYPE_CHECKING or settings.is_development() or settings.is_testing():

    class PresentmentCurrency(StrEnum):
        aud = "aud"
        brl = "brl"
        cad = "cad"
        chf = "chf"
        eur = "eur"
        inr = "inr"
        gbp = "gbp"
        jpy = "jpy"
        sek = "sek"
        usd = "usd"
else:
    # For now, only USD is supported in production
    class PresentmentCurrency(StrEnum):
        usd = "usd"


# ── Formatting ──

_CURRENCY_DECIMAL_FACTORS: dict[str, int] = {
    "aud": 100,
    "cad": 100,
    "chf": 100,
    "eur": 100,
    "inr": 100,
    "gbp": 100,
    "jpy": 1,
    "sek": 100,
    "usd": 100,
}


def format_currency(
    amount: int | Decimal | float,
    currency: PresentmentCurrency | str,
    decimal_quantization: bool = True,
) -> str:
    """Format the currency amount.

    Handles conversion from smallest currency unit (e.g., cents) to major unit.

    Args:
        amount: The amount in the smallest currency unit (e.g., cents).
        currency: The currency code.
        decimal_quantization: Truncate and round high-precision numbers to the format pattern.

    Returns:
        The formatted currency string.
    """
    return _format_currency(
        amount / _CURRENCY_DECIMAL_FACTORS[currency],
        currency.upper(),
        locale="en_US",
        decimal_quantization=decimal_quantization,
    )
