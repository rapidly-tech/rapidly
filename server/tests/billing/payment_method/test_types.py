"""Tests for ``rapidly/billing/payment_method/types.py``.

Payment-method request / response models. Four load-bearing surfaces:

- ``PaymentMethodCreate.return_url`` runs through
  ``get_safe_return_url`` as an ``AfterValidator`` — the
  open-redirect defence for the 3D-Secure verification flow.
  An attacker-supplied off-host URL gets rewritten to the
  default. Drift in the validator binding would silently let
  the attacker phish customers post-3DS.
- ``PaymentMethodCreate.set_default`` and
  ``PaymentMethodConfirm.set_default`` BOTH default to ``True``
  — drift to ``False`` would silently change first-card UX
  (customer's card saved but not active for next checkout).
- ``PaymentMethodCreateResponse`` is a discriminated union:
  succeeded (with PaymentMethodSchema) vs requires_action (with
  client_secret). The ``status`` Literal pins the wire
  discriminator. Drift would let the frontend mis-route the
  3DS flow.
- ``PaymentMethodSchema`` field defaults: ``is_default=False``,
  optional ``brand`` / ``last4`` / ``exp_month`` / ``exp_year``.
  These are documented contract guarantees — drift to
  required-field would crash for non-card payment methods
  (us_bank_account etc. don't have a brand).
"""

from __future__ import annotations

from datetime import UTC
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from rapidly.billing.payment_method.types import (
    PaymentMethodConfirm,
    PaymentMethodCreate,
    PaymentMethodCreateRequiresActionResponse,
    PaymentMethodCreateResponse,
    PaymentMethodCreateSucceededResponse,
    PaymentMethodSchema,
)
from rapidly.enums import PaymentProcessor


def _now() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def _payment_method_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": str(uuid4()),
        "created_at": _now(),
        "modified_at": _now(),
        "processor": PaymentProcessor.stripe,
        "type": "card",
    }
    base.update(overrides)
    return base


class TestPaymentMethodSchema:
    def test_card_with_full_details(self) -> None:
        # Pin: a card payment method round-trips with brand /
        # last4 / exp_month / exp_year populated.
        pm = PaymentMethodSchema.model_validate(
            _payment_method_payload(
                brand="visa",
                last4="4242",
                exp_month=12,
                exp_year=2030,
                is_default=True,
            )
        )
        assert pm.brand == "visa"
        assert pm.last4 == "4242"
        assert pm.exp_month == 12
        assert pm.exp_year == 2030
        assert pm.is_default is True

    def test_non_card_methods_omit_brand_and_last4(self) -> None:
        # Pin: brand / last4 / exp_month / exp_year are OPTIONAL
        # so non-card processors (us_bank_account, sepa_debit)
        # validate. Drift to required-field would 422 every
        # ACH / bank payment.
        pm = PaymentMethodSchema.model_validate(
            _payment_method_payload(type="us_bank_account")
        )
        assert pm.brand is None
        assert pm.last4 is None
        assert pm.exp_month is None
        assert pm.exp_year is None

    def test_is_default_defaults_to_false(self) -> None:
        # Pin: ``is_default`` defaults to False. Drift to True
        # would silently make every newly-saved card the default.
        pm = PaymentMethodSchema.model_validate(_payment_method_payload())
        assert pm.is_default is False


class TestPaymentMethodCreate:
    def test_set_default_defaults_to_true(self) -> None:
        # Pin: a customer's first card MUST become the default
        # by default. Drift to False breaks the documented
        # first-checkout flow.
        body = PaymentMethodCreate(
            confirmation_token_id="ctk_123",
            return_url="https://x.com",
        )
        assert body.set_default is True

    def test_safe_return_url_passes_through_allowed_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: return_url runs through ``get_safe_return_url``.
        # An ALLOWED host passes through unchanged.
        from rapidly.config import settings

        monkeypatch.setattr(
            settings, "ALLOWED_HOSTS", ["app.rapidly.tech", "rapidly.tech"]
        )
        body = PaymentMethodCreate(
            confirmation_token_id="ctk_123",
            return_url="https://app.rapidly.tech/billing",
        )
        assert body.return_url == "https://app.rapidly.tech/billing"

    def test_unsafe_return_url_rewritten_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Load-bearing security pin: an attacker-supplied off-host
        # URL gets REWRITTEN to the default frontend URL, NOT
        # passed through. Drift would let an attacker steal
        # the post-3DS redirect for phishing.
        from rapidly.config import settings

        monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["app.rapidly.tech"])
        body = PaymentMethodCreate(
            confirmation_token_id="ctk_123",
            return_url="https://attacker.example.com/steal",
        )
        # Sanitised — no longer the attacker URL.
        assert "attacker.example.com" not in body.return_url


class TestPaymentMethodConfirm:
    def test_set_default_defaults_to_true(self) -> None:
        # Same first-card UX pin as create.
        body = PaymentMethodConfirm(setup_intent_id="seti_123")
        assert body.set_default is True

    def test_setup_intent_id_required(self) -> None:
        # Pin: setup_intent_id is required (no default).
        with pytest.raises(ValidationError):
            PaymentMethodConfirm()  # type: ignore[call-arg]


class TestSucceededResponse:
    def test_status_literal(self) -> None:
        # Pin the wire discriminator value. Drift would break
        # frontend's branch on response.status.
        pm = PaymentMethodSchema.model_validate(_payment_method_payload())
        resp = PaymentMethodCreateSucceededResponse(payment_method=pm)
        assert resp.status == "succeeded"

    def test_status_default_is_succeeded(self) -> None:
        # Pin: default value lets callers omit status — Pydantic
        # writes it for them on serialisation.
        pm = PaymentMethodSchema.model_validate(_payment_method_payload())
        resp = PaymentMethodCreateSucceededResponse(payment_method=pm)
        dumped = resp.model_dump()
        assert dumped["status"] == "succeeded"


class TestRequiresActionResponse:
    def test_status_literal(self) -> None:
        resp = PaymentMethodCreateRequiresActionResponse(
            client_secret="seti_123_secret_xyz"
        )
        assert resp.status == "requires_action"

    def test_client_secret_required(self) -> None:
        # Pin: client_secret is required — without it, the
        # frontend can't complete 3DS verification.
        with pytest.raises(ValidationError):
            PaymentMethodCreateRequiresActionResponse()  # type: ignore[call-arg]


class TestPaymentMethodCreateResponseUnion:
    def test_succeeded_dispatches_to_succeeded_class(self) -> None:
        # Pin: union-validation correctly dispatches based on the
        # status field. Drift in either Literal would let an
        # attacker spoof one response class with another.
        adapter: TypeAdapter[PaymentMethodCreateResponse] = TypeAdapter(
            PaymentMethodCreateResponse
        )
        result = adapter.validate_python(
            {
                "status": "succeeded",
                "payment_method": _payment_method_payload(),
            }
        )
        assert isinstance(result, PaymentMethodCreateSucceededResponse)

    def test_requires_action_dispatches_to_requires_action_class(self) -> None:
        adapter: TypeAdapter[PaymentMethodCreateResponse] = TypeAdapter(
            PaymentMethodCreateResponse
        )
        result = adapter.validate_python(
            {"status": "requires_action", "client_secret": "seti_x_secret"}
        )
        assert isinstance(result, PaymentMethodCreateRequiresActionResponse)

    def test_unknown_status_rejected(self) -> None:
        # Pin: an unknown status string is rejected. Drift to
        # silently accept it would let the frontend show stale
        # data on a 3DS failure path.
        adapter: TypeAdapter[PaymentMethodCreateResponse] = TypeAdapter(
            PaymentMethodCreateResponse
        )
        with pytest.raises(ValidationError):
            adapter.validate_python({"status": "weird", "client_secret": "x"})
