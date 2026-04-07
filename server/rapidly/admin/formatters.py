"""Display formatters for dates, currency, and status values in the admin panel.

Each function transforms a raw Python value into a human-readable string
suitable for rendering inside Jinja2 templates or DaisyUI data tables.
"""

from __future__ import annotations

from datetime import datetime as dt
from decimal import Decimal

from rapidly.core.currency import format_currency
from rapidly.core.utils import human_readable_size

# ── Date/time ────────────────────────────────────────────────────────


def datetime(value: dt) -> str:
    """Format a datetime as ``YYYY-MM-DD HH:MM:SS``."""
    return value.strftime("%Y-%m-%d %H:%M:%S")


# ── Money ────────────────────────────────────────────────────────────


def currency(
    value: int | Decimal | float,
    currency: str,
    *,
    decimal_quantization: bool = True,
) -> str:
    """Render a monetary amount using locale-aware currency formatting."""
    return format_currency(value, currency, decimal_quantization=decimal_quantization)


# ── File sizes ───────────────────────────────────────────────────────


def file_size(size_bytes: int) -> str:
    """Format a byte count to a compact human-readable string (e.g. ``4.2 MB``).

    Delegates to :func:`rapidly.core.utils.human_readable_size` but preserves
    the admin convention of omitting the decimal for sub-KB values.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    return human_readable_size(size_bytes)
