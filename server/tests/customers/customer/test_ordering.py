"""Tests for ``rapidly/customers/customer/ordering.py``."""

from __future__ import annotations

from rapidly.customers.customer.ordering import CustomerSortProperty


class TestCustomerSortProperty:
    def test_exposes_documented_columns(self) -> None:
        assert {e.value for e in CustomerSortProperty} == {
            "email",
            "name",
            "created_at",
        }

    def test_customer_name_attribute_alias(self) -> None:
        # StrEnum reserved-word workaround: attribute is
        # ``customer_name``, on-wire value is ``"name"``. Pinned so the
        # DB column + saved sort params stay aligned.
        assert CustomerSortProperty.customer_name.value == "name"

    def test_is_str_enum(self) -> None:
        assert str(CustomerSortProperty.email) == "email"
