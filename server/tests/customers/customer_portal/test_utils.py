"""Tests for ``rapidly/customers/customer_portal/utils.py``.

Customer-portal auth-subject extractors. Two load-bearing surfaces:

- ``get_customer`` MUST handle BOTH ``Customer`` and ``Member``
  principals — Customer principals are direct token-holders;
  Member principals are workspace members acting on behalf of a
  customer (member.customer association). Drift would crash one
  branch silently and lock out half the portal users.
- An unknown subject type raises ``TypeError`` loudly (NOT
  silently returns ``None`` or raises ``AttributeError``).
  Otherwise a refactor that introduced a third subject type
  would fail open: portal endpoints would return data scoped to
  ``None``, which queries would interpret as "no scope" and
  potentially leak cross-tenant data.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from rapidly.customers.customer_portal.utils import get_customer, get_customer_id
from rapidly.identity.auth.models import Member
from rapidly.models import Customer as CustomerModel


def _customer(*, id_: UUID | None = None) -> MagicMock:
    """Build a Customer-spec'd MagicMock so isinstance(subject, Customer)
    returns True without needing a real SQLAlchemy session-bound instance."""
    c = MagicMock(spec=CustomerModel)
    c.id = id_ if id_ is not None else uuid4()
    return c


def _member(*, customer: MagicMock) -> MagicMock:
    m = MagicMock(spec=Member)
    m.customer = customer
    return m


class TestGetCustomerForCustomerPrincipal:
    def test_returns_subject_directly(self) -> None:
        # Pin: when the principal IS the Customer, we return it
        # unchanged (no member-association lookup needed).
        cust = _customer()
        principal = SimpleNamespace(subject=cust)
        assert get_customer(principal) is cust  # type: ignore[arg-type]


class TestGetCustomerForMemberPrincipal:
    def test_returns_member_dot_customer(self) -> None:
        # Pin: when the principal is a Member, return
        # ``member.customer``. Drift to ``member`` itself would
        # leak member-scoped data through customer-scoped queries
        # (cross-tenant data leak).
        cust = _customer()
        member = _member(customer=cust)
        principal = SimpleNamespace(subject=member)
        assert get_customer(principal) is cust  # type: ignore[arg-type]


class TestGetCustomerForUnknownSubject:
    def test_raises_type_error_loudly(self) -> None:
        # Pin (security): an unknown principal type MUST raise
        # TypeError, NOT silently return None / fall through.
        # Otherwise a third subject type added later would fail
        # open and leak cross-tenant data.
        principal = SimpleNamespace(subject="not a customer or member")
        with pytest.raises(TypeError, match="Unexpected auth subject"):
            get_customer(principal)  # type: ignore[arg-type]

    def test_error_message_mentions_actual_type(self) -> None:
        # Pin: error message includes the offending type name so
        # logs are actionable.
        principal = SimpleNamespace(subject=42)
        with pytest.raises(TypeError, match="int"):
            get_customer(principal)  # type: ignore[arg-type]


class TestGetCustomerId:
    def test_returns_id_for_customer_principal(self) -> None:
        # Pin: ``get_customer_id`` is a thin wrapper around
        # ``get_customer().id``. Drift to a different attribute
        # name would crash every portal endpoint.
        target_id = uuid4()
        cust = _customer(id_=target_id)
        principal = SimpleNamespace(subject=cust)
        assert get_customer_id(principal) == target_id  # type: ignore[arg-type]

    def test_returns_id_for_member_principal(self) -> None:
        # Pin: same delegation works through the Member branch.
        target_id = uuid4()
        cust = _customer(id_=target_id)
        member = _member(customer=cust)
        principal = SimpleNamespace(subject=member)
        assert get_customer_id(principal) == target_id  # type: ignore[arg-type]
