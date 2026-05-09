"""Tests for ``rapidly/billing/payment/ordering.py``."""

from __future__ import annotations

from rapidly.billing.payment.ordering import PaymentSortProperty


class TestPaymentSortProperty:
    def test_exposes_documented_columns(self) -> None:
        assert {e.value for e in PaymentSortProperty} == {
            "created_at",
            "status",
            "amount",
            "method",
        }

    def test_is_str_enum(self) -> None:
        assert str(PaymentSortProperty.amount) == "amount"
