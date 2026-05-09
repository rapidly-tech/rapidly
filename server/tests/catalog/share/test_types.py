"""Tests for ``rapidly/catalog/share/types.py``.

Complements the existing ``test_schemas.py`` (name length only) with
pins on the share-creation invariants that actually bound money and
discrimination flows:

- **Price-amount bounds** — ``MINIMUM_PRICE_AMOUNT = 2000`` (i.e.
  $20) and ``MAXIMUM_PRICE_AMOUNT = 99_999_999`` (just under $1 M).
  A regression widening either would let a caller pin a fixed price
  Stripe refuses, or an absurdly high amount that clears
  PaymentIntent-limits only on some accounts.
- **``SharePriceCustomCreate.validate_amount_not_in_minimum_gap``**:
  0 (free/pay-what-you-want) is OK, 1..MIN-1 is rejected, MIN is
  OK. The comment in the code talks about a ``$0.50`` minimum but
  the code actually uses ``MINIMUM_PRICE_AMOUNT`` (currently $20) —
  pinning via the CONSTANT, not a literal, so the test stays
  correct if the gap moves.
- **``SharePriceCreate`` discriminator** on ``amount_type``
  (fixed / custom / free)
- **``SharePriceCreateList`` min_length=1** — a share with no
  prices is invalid
- **``ShareCreate.visibility`` defaults to ``public``**, NOT
  ``draft`` — a silent flip would hide every newly-created share
- **``ExistingSharePrice`` union-mode on SharePriceUpdate** is
  ``left_to_right`` so a body with only ``id`` selects the
  "keep existing" branch, not the Create branch (which would 422
  on the missing required fields)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from rapidly.catalog.share.types import (
    MAXIMUM_PRICE_AMOUNT,
    MINIMUM_PRICE_AMOUNT,
    SHARE_NAME_MIN_LENGTH,
    ExistingSharePrice,
    ShareCreate,
    SharePriceCreate,
    SharePriceCustomCreate,
    SharePriceFixedCreate,
    SharePriceFreeCreate,
    SharePriceUpdate,
)
from rapidly.core.currency import PresentmentCurrency
from rapidly.models.share import ShareVisibility
from rapidly.models.share_price import SharePriceAmountType


def _fixed_price(amount: int = 2000) -> SharePriceFixedCreate:
    return SharePriceFixedCreate(
        amount_type=SharePriceAmountType.fixed,
        price_amount=amount,
        price_currency=PresentmentCurrency.usd,
    )


# ── Constants ──


class TestConstants:
    def test_minimum_and_maximum_pinned(self) -> None:
        # Pin the documented money bounds so drift surfaces via
        # this test, not via a Stripe PaymentIntent error in prod.
        assert MINIMUM_PRICE_AMOUNT == 2000
        assert MAXIMUM_PRICE_AMOUNT == 99_999_999

    def test_share_name_min_length_is_3(self) -> None:
        assert SHARE_NAME_MIN_LENGTH == 3


# ── Fixed-price bounds ──


class TestFixedPriceBounds:
    def test_accepts_minimum(self) -> None:
        _fixed_price(MINIMUM_PRICE_AMOUNT)

    def test_accepts_maximum(self) -> None:
        _fixed_price(MAXIMUM_PRICE_AMOUNT)

    def test_rejects_below_minimum(self) -> None:
        with pytest.raises(ValidationError):
            _fixed_price(MINIMUM_PRICE_AMOUNT - 1)

    def test_rejects_above_maximum(self) -> None:
        with pytest.raises(ValidationError):
            _fixed_price(MAXIMUM_PRICE_AMOUNT + 1)


# ── Custom-price minimum-gap validator ──


class TestCustomPriceMinimumGap:
    def test_zero_is_accepted(self) -> None:
        # ``0`` means free / pay-what-you-want starting at $0.
        SharePriceCustomCreate(
            amount_type=SharePriceAmountType.custom,
            price_currency=PresentmentCurrency.usd,
            minimum_amount=0,
        )

    def test_gap_value_is_rejected(self) -> None:
        # Anything 1..MIN-1 is in the gap — rejected.
        with pytest.raises(ValidationError):
            SharePriceCustomCreate(
                amount_type=SharePriceAmountType.custom,
                price_currency=PresentmentCurrency.usd,
                minimum_amount=MINIMUM_PRICE_AMOUNT - 1,
            )

    def test_minimum_is_accepted(self) -> None:
        SharePriceCustomCreate(
            amount_type=SharePriceAmountType.custom,
            price_currency=PresentmentCurrency.usd,
            minimum_amount=MINIMUM_PRICE_AMOUNT,
        )

    def test_preset_in_gap_is_rejected(self) -> None:
        # The validator applies to BOTH ``minimum_amount`` and
        # ``preset_amount``. A regression that only checked one
        # would leak through on the other field.
        with pytest.raises(ValidationError):
            SharePriceCustomCreate(
                amount_type=SharePriceAmountType.custom,
                price_currency=PresentmentCurrency.usd,
                preset_amount=MINIMUM_PRICE_AMOUNT - 1,
            )


# ── Discriminated union ──


class TestSharePriceCreateDiscriminator:
    _Adapter: TypeAdapter[SharePriceCreate] = TypeAdapter(SharePriceCreate)

    def test_fixed_dispatch(self) -> None:
        body = self._Adapter.validate_python(
            {
                "amount_type": "fixed",
                "price_amount": 2000,
                "price_currency": "usd",
            }
        )
        assert isinstance(body, SharePriceFixedCreate)

    def test_custom_dispatch(self) -> None:
        body = self._Adapter.validate_python(
            {"amount_type": "custom", "price_currency": "usd"}
        )
        assert isinstance(body, SharePriceCustomCreate)

    def test_free_dispatch(self) -> None:
        body = self._Adapter.validate_python(
            {"amount_type": "free", "price_currency": "usd"}
        )
        assert isinstance(body, SharePriceFreeCreate)

    def test_unknown_amount_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._Adapter.validate_python(
                {"amount_type": "subscription", "price_currency": "usd"}
            )


# ── ShareCreate defaults ──


class TestShareCreateDefaults:
    def test_visibility_defaults_to_public(self) -> None:
        # Load-bearing UX default. A silent flip to ``draft`` would
        # hide every newly-created share behind the dashboard's
        # "published" filter — callers would think their API-created
        # shares aren't reaching customers.
        body = ShareCreate(
            name="Report",
            prices=[_fixed_price()],
        )
        assert body.visibility == ShareVisibility.public

    def test_requires_at_least_one_price(self) -> None:
        # ``SharePriceCreateList`` has ``Field(min_length=1)``. A
        # zero-price share has no way to charge — the validator
        # must reject it at the API boundary.
        with pytest.raises(ValidationError):
            ShareCreate(name="Report", prices=[])

    def test_attached_custom_fields_defaults_to_empty(self) -> None:
        body = ShareCreate(name="Report", prices=[_fixed_price()])
        assert body.attached_custom_fields == []

    def test_description_empty_string_coerces_to_none(self) -> None:
        # ``ShareDescription`` uses ``EmptyStrToNoneValidator`` —
        # callers who submit an empty description must have it
        # persisted as None so the storefront doesn't render an
        # empty <p> tag.
        body = ShareCreate(name="Report", description="   ", prices=[_fixed_price()])
        assert body.description is None


# ── SharePriceUpdate union shape ──


class TestSharePriceUpdateUnionLeftToRight:
    _Adapter: TypeAdapter[SharePriceUpdate] = TypeAdapter(SharePriceUpdate)

    def test_bare_id_selects_existing_branch(self) -> None:
        # ``SharePriceUpdate = ExistingSharePrice | SharePriceCreate``
        # with ``union_mode="left_to_right"``. A body with only an
        # id must pick the ``ExistingSharePrice`` branch — the
        # Create branch would fail on the missing required
        # ``amount_type`` / ``price_currency`` fields.
        body = self._Adapter.validate_python({"id": str(uuid4())})
        assert isinstance(body, ExistingSharePrice)

    def test_create_body_selects_create_branch(self) -> None:
        body = self._Adapter.validate_python(
            {"amount_type": "free", "price_currency": "usd"}
        )
        assert isinstance(body, SharePriceFreeCreate)
