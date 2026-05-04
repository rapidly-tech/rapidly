"""Numerical utilities for monetary and balance calculations.

``rapidly_round``
    Round-half-away-from-zero (the intuitive rounding humans expect on
    invoices), unlike Python's built-in ``round`` which uses banker's
    rounding (half-to-even).
"""

import math
from decimal import Decimal


def rapidly_round(number: int | float | Decimal) -> int:
    """Round to nearest integer; half-values go away from zero.

    >>> rapidly_round(8.5)
    9
    >>> rapidly_round(-8.5)
    -9

    Python's built-in ``round(0.5)`` returns ``0`` (banker's rounding),
    which surprises users on price displays.  This function always rounds
    ``0.5`` away from zero.
    """
    fractional = number - int(number)
    if number >= 0:
        return math.ceil(number) if fractional >= 0.5 else math.floor(number)
    return math.floor(number) if fractional <= -0.5 else math.ceil(number)
