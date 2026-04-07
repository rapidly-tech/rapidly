"""Tests for share Pydantic schemas."""

import pytest
from pydantic import ValidationError

from rapidly.catalog.share.types import (
    ShareCreate,
    SharePriceFixedCreate,
)
from rapidly.core.currency import PresentmentCurrency
from rapidly.models.share_price import SharePriceAmountType


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("", id="empty string"),
        pytest.param("AA", id="below min length"),
    ],
)
def test_invalid_product_name(name: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ShareCreate(
            name=name,
            prices=[
                SharePriceFixedCreate(
                    amount_type=SharePriceAmountType.fixed,
                    price_amount=1000,
                    price_currency=PresentmentCurrency.usd,
                )
            ],
        )

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] in ("string_too_short", "string_too_long")
    assert errors[0]["loc"] == ("name",)


def test_valid_product_name() -> None:
    share = ShareCreate(
        name="Valid Share Name",
        prices=[
            SharePriceFixedCreate(
                amount_type=SharePriceAmountType.fixed,
                price_amount=1000,
                price_currency=PresentmentCurrency.usd,
            )
        ],
    )
    assert share.name == "Valid Share Name"
