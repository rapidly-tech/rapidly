"""Tests for ``rapidly/catalog/share/guard.py``.

Type guards for the SharePrice polymorphic hierarchy. Three
load-bearing surfaces:

- The four guards (``is_fixed_price`` / ``is_custom_price`` /
  ``is_free_price`` / ``is_static_price``) are mutually
  consistent — for any given concrete price subclass only the
  matching guard returns True (drift to a wider ``isinstance``
  check would mis-route the catalog renderer between
  fixed/custom/free templates).
- ``is_static_price`` delegates to the price's ``is_static``
  hybrid property — drift to hardcode a class list here would
  miss new "static" subclasses (seat-based) that the model
  layer adds.
- The guards are PEP-647 ``TypeIs`` narrowing functions — the
  return type narrows the caller's static-typed reference to
  the documented variant, so downstream code can access
  variant-specific fields without ``# type: ignore``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from rapidly.catalog.share.guard import (
    is_custom_price,
    is_fixed_price,
    is_free_price,
    is_static_price,
)
from rapidly.models import (
    SharePriceCustom,
    SharePriceFixed,
    SharePriceFree,
)


def _make(cls: type, *, is_static: bool = True) -> object:
    """Create a SharePrice* instance bypassing __init__ + the
    is_static hybrid property's value side."""
    obj = MagicMock(spec=cls)
    obj.is_static = is_static
    # Make ``isinstance(obj, cls)`` return True via spec.
    return obj


class TestPriceTypeGuards:
    def test_fixed_price_only_matches_is_fixed(self) -> None:
        # Pin: the FIXED variant matches only ``is_fixed_price``.
        # Drift to a wider ``isinstance`` check would mis-route
        # the catalog renderer.
        price = _make(SharePriceFixed)
        assert is_fixed_price(price) is True  # type: ignore[arg-type]
        assert is_custom_price(price) is False  # type: ignore[arg-type]
        assert is_free_price(price) is False  # type: ignore[arg-type]

    def test_custom_price_only_matches_is_custom(self) -> None:
        price = _make(SharePriceCustom)
        assert is_fixed_price(price) is False  # type: ignore[arg-type]
        assert is_custom_price(price) is True  # type: ignore[arg-type]
        assert is_free_price(price) is False  # type: ignore[arg-type]

    def test_free_price_only_matches_is_free(self) -> None:
        price = _make(SharePriceFree)
        assert is_fixed_price(price) is False  # type: ignore[arg-type]
        assert is_custom_price(price) is False  # type: ignore[arg-type]
        assert is_free_price(price) is True  # type: ignore[arg-type]


class TestIsStaticPriceDelegation:
    def test_static_returns_true_for_static_hybrid(self) -> None:
        # Pin: ``is_static_price`` delegates to ``price.is_static``.
        # Drift to hardcode a class list would miss any new
        # "static" subclass (seat-based) that the model adds.
        price = MagicMock()
        price.is_static = True
        assert is_static_price(price) is True

    def test_static_returns_false_when_hybrid_false(self) -> None:
        # Pin: a metered-unit price has ``is_static=False``;
        # the guard MUST mirror.
        price = MagicMock()
        price.is_static = False
        assert is_static_price(price) is False
