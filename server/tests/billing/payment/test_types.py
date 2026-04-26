"""Tests for ``rapidly/billing/payment/types.py``.

``Payment = Annotated[CardPayment | GenericPayment, ...]`` is a
**plain (non-discriminated) union** — Pydantic attempts ``CardPayment``
first because it's listed first, and falls back to ``GenericPayment``
when ``method != "card"``. Pinning the dispatch behaviour catches
two kinds of regression:

1. Swapping the union order (``GenericPayment | CardPayment`` would
   greedily accept the ``GenericPayment`` variant and drop the
   ``method_metadata`` field on card payments).
2. Converting the pair to a plain ``dict`` response (the typed split
   is what makes the card metadata discoverable in the OpenAPI
   schema).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rapidly.billing.payment.types import (
    CardPayment,
    CardPaymentMetadata,
    GenericPayment,
    PaymentAdapter,
)
from rapidly.enums import PaymentProcessor
from rapidly.models.payment import PaymentStatus


def _base_body(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    body: dict[str, Any] = {
        "id": str(uuid4()),
        "created_at": now,
        "modified_at": now,
        "processor": PaymentProcessor.stripe.value,
        "status": PaymentStatus.succeeded.value,
        "amount": 1000,
        "currency": "usd",
        "method": "card",
        "decline_reason": None,
        "decline_message": None,
        "workspace_id": str(uuid4()),
    }
    body.update(overrides)
    return body


class TestCardPaymentMetadata:
    def test_requires_brand_and_last4(self) -> None:
        with pytest.raises(ValidationError):
            CardPaymentMetadata.model_validate({"brand": "visa"})
        with pytest.raises(ValidationError):
            CardPaymentMetadata.model_validate({"last4": "4242"})


class TestPaymentAdapterDispatch:
    def test_card_payment_with_metadata_picks_card_branch(self) -> None:
        # ``method="card"`` + ``method_metadata`` → CardPayment.
        body = _base_body(
            method="card",
            method_metadata={"brand": "visa", "last4": "4242"},
        )
        result = PaymentAdapter.validate_python(body)
        assert isinstance(result, CardPayment)
        assert result.method_metadata.brand == "visa"
        assert result.method_metadata.last4 == "4242"

    def test_non_card_method_picks_generic_branch(self) -> None:
        # ``method="bank_transfer"`` cannot match CardPayment (the
        # Literal["card"] rejects it), so GenericPayment picks it up.
        body = _base_body(method="bank_transfer")
        result = PaymentAdapter.validate_python(body)
        assert isinstance(result, GenericPayment)
        assert result.method == "bank_transfer"


class TestCardPaymentMethodLiteral:
    def test_rejects_non_card_method_on_card_branch(self) -> None:
        # Directly validating against CardPayment must reject
        # ``method != "card"`` — pinning the Literal stops a future
        # refactor that widens the field to ``str`` from silently
        # accepting bank payments into the card branch.
        body = _base_body(
            method="bank_transfer",
            method_metadata={"brand": "visa", "last4": "4242"},
        )
        with pytest.raises(ValidationError):
            CardPayment.model_validate(body)


class TestProcessorMetadataDefault:
    def test_defaults_to_empty_dict(self) -> None:
        # ``processor_metadata`` is an internal debugging field.
        # Pinning the default-empty-dict keeps the dashboard row
        # expander stable when the processor didn't populate anything.
        body = _base_body(method="cash")
        body.pop("processor_metadata", None)
        result = PaymentAdapter.validate_python(body)
        assert result.processor_metadata == {}


class TestPaymentAdapterIsPreBuilt:
    def test_module_level_adapter_exists(self) -> None:
        # ``PaymentAdapter`` is the module-level TypeAdapter — API
        # code uses it to validate the union; a regression that
        # inlined ``TypeAdapter(Payment)`` per request would add
        # overhead to every payment list response.
        from pydantic import TypeAdapter

        assert isinstance(PaymentAdapter, TypeAdapter)
