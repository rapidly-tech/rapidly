"""Tests for ``rapidly/billing/stripe_connect/types.py``.

Four small response schemas that mirror Stripe Connect balance and
payout shapes. Small, but pinning the required-field discipline
prevents a regression that accepts a malformed Stripe response and
500s deeper downstream.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rapidly.billing.stripe_connect.types import (
    StripeBalance,
    StripeBalanceAmount,
    StripePayout,
    StripePayoutList,
)


class TestStripeBalanceAmount:
    def test_requires_amount_and_currency(self) -> None:
        with pytest.raises(ValidationError):
            StripeBalanceAmount.model_validate({"amount": 1000})
        with pytest.raises(ValidationError):
            StripeBalanceAmount.model_validate({"currency": "usd"})

    def test_roundtrip(self) -> None:
        body = StripeBalanceAmount(amount=1000, currency="usd")
        assert body.amount == 1000
        assert body.currency == "usd"


class TestStripeBalance:
    def test_accepts_empty_lists(self) -> None:
        # Fresh accounts report empty available/pending balances —
        # the schema must not require at least one entry.
        body = StripeBalance(available=[], pending=[])
        assert body.available == []
        assert body.pending == []

    def test_requires_both_fields(self) -> None:
        with pytest.raises(ValidationError):
            StripeBalance.model_validate({"available": []})


class TestStripePayout:
    def _valid(self) -> dict[str, object]:
        return {
            "id": "po_1",
            "amount": 5000,
            "currency": "usd",
            "status": "paid",
            "arrival_date": datetime.now(UTC),
            "created": datetime.now(UTC),
            "method": "standard",
        }

    def test_description_is_optional(self) -> None:
        # Stripe's payout objects may or may not carry a human-
        # readable description. Required would reject valid Stripe
        # responses.
        body = StripePayout.model_validate(self._valid())
        assert body.description is None

    def test_requires_core_fields(self) -> None:
        for field in ("id", "amount", "currency", "status", "arrival_date", "method"):
            body = self._valid()
            del body[field]
            with pytest.raises(ValidationError):
                StripePayout.model_validate(body)


class TestStripePayoutList:
    def test_roundtrip(self) -> None:
        body = StripePayoutList(items=[], has_more=False)
        assert body.items == []
        assert body.has_more is False

    def test_requires_has_more(self) -> None:
        # Pagination flag must be explicit — Stripe returns it on
        # every list response and the TS client relies on it for
        # the "Load more" button.
        with pytest.raises(ValidationError):
            StripePayoutList.model_validate({"items": []})
