"""Tests for ``rapidly/customers/customer_session/types.py``.

Customer sessions are the impersonation / ephemeral-token primitive
that lets a workspace mint portal-access tokens on a customer's
behalf. The types carry several load-bearing contracts:

- ``CustomerSessionCreate`` is a union: either ``customer_id`` or
  ``external_customer_id`` must be supplied — a payload with neither
  must 422 (otherwise the API would accept an ambiguous request).
- ``external_customer_id`` accepts BOTH ``external_customer_id``
  and the legacy ``customer_external_id`` alias — a regression
  dropping the alias would break clients that still send the old key.
- ``return_url`` is typed ``HttpUrl | None`` — same portal-anchor
  XSS defence pinned on member_session (Phase 117). ``javascript:``
  / bare paths must be rejected at the API boundary.
- ``CustomerSession.token`` uses ``validation_alias="raw_token"`` —
  the single-shot raw-token delivery contract (same shape as
  member_session).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from rapidly.customers.customer_session.types import (
    CustomerSession,
    CustomerSessionCreate,
    CustomerSessionCustomerExternalIDCreate,
    CustomerSessionCustomerIDCreate,
)


class TestCustomerSessionCustomerIDCreate:
    def test_requires_customer_id(self) -> None:
        with pytest.raises(ValidationError):
            CustomerSessionCustomerIDCreate.model_validate({})

    def test_accepts_valid_uuid(self) -> None:
        body = CustomerSessionCustomerIDCreate(customer_id=uuid4())
        assert body.customer_id is not None


class TestCustomerSessionCustomerExternalIDCreate:
    def test_requires_external_customer_id(self) -> None:
        with pytest.raises(ValidationError):
            CustomerSessionCustomerExternalIDCreate.model_validate({})

    def test_canonical_key(self) -> None:
        body = CustomerSessionCustomerExternalIDCreate.model_validate(
            {"external_customer_id": "cust_123"}
        )
        assert body.external_customer_id == "cust_123"

    def test_legacy_alias_still_accepted(self) -> None:
        # ``validation_alias=AliasChoices("external_customer_id",
        # "customer_external_id")`` — the legacy key must still
        # round-trip. Removing it would break SDKs that haven't
        # migrated to the new name.
        body = CustomerSessionCustomerExternalIDCreate.model_validate(
            {"customer_external_id": "cust_123"}
        )
        assert body.external_customer_id == "cust_123"


class TestCustomerSessionCreateUnion:
    _Adapter: TypeAdapter[CustomerSessionCreate] = TypeAdapter(CustomerSessionCreate)

    def test_dispatches_to_customer_id_branch(self) -> None:
        body = self._Adapter.validate_python({"customer_id": str(uuid4())})
        assert isinstance(body, CustomerSessionCustomerIDCreate)

    def test_dispatches_to_external_id_branch(self) -> None:
        body = self._Adapter.validate_python({"external_customer_id": "cust_123"})
        assert isinstance(body, CustomerSessionCustomerExternalIDCreate)

    def test_rejects_empty_payload(self) -> None:
        # Neither id field supplied — both union branches require
        # their own id, so an empty body must fail.
        with pytest.raises(ValidationError):
            self._Adapter.validate_python({})


class TestReturnUrlSafety:
    def test_rejects_javascript_scheme(self) -> None:
        # Same portal-anchor XSS defence pinned on member_session.
        # A regression to ``str`` would let a crafted session
        # persist ``javascript:`` and render it as the back-button
        # anchor.
        with pytest.raises(ValidationError):
            CustomerSessionCustomerIDCreate.model_validate(
                {
                    "customer_id": str(uuid4()),
                    "return_url": "javascript:alert(1)",
                }
            )

    def test_rejects_bare_path(self) -> None:
        with pytest.raises(ValidationError):
            CustomerSessionCustomerIDCreate.model_validate(
                {"customer_id": str(uuid4()), "return_url": "/account"}
            )

    def test_accepts_https(self) -> None:
        body = CustomerSessionCustomerIDCreate.model_validate(
            {
                "customer_id": str(uuid4()),
                "return_url": "https://customer.example/account",
            }
        )
        assert body.return_url is not None


class TestCustomerSessionReadModel:
    def test_token_uses_raw_token_alias(self) -> None:
        # Mirrors member_session: the ORM exposes the pre-hashed raw
        # token only on creation via ``raw_token``; the API surfaces
        # it on the response once. A rename on either side breaks
        # the single-shot token-delivery contract.
        field = CustomerSession.model_fields["token"]
        assert field.validation_alias == "raw_token"


class TestMemberIdOnCreate:
    # member_id / external_member_id are optional, gated by
    # member_model_enabled on the workspace. Pinning the absence
    # of a required constraint prevents a regression that made
    # either mandatory and broke the default customer-session flow.
    def test_member_fields_optional_on_customer_id_branch(self) -> None:
        body = CustomerSessionCustomerIDCreate(customer_id=uuid4())
        assert body.member_id is None
        assert body.external_member_id is None

    def test_member_fields_optional_on_external_branch(self) -> None:
        body = CustomerSessionCustomerExternalIDCreate(external_customer_id="x")
        assert body.member_id is None
        assert body.external_member_id is None
