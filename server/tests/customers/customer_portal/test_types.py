"""Tests for ``rapidly/customers/customer_portal/types/*.py``.

Pins the three customer-portal types files (customer, member,
customer_session) in one bundle. Each carries a small number of
load-bearing contracts:

- ``CustomerPortalMemberCreate.role`` defaults to
  ``MemberRole.member`` — NOT ``owner`` or ``billing_manager``.
  The portal is the self-service path for team-admin to add
  members; a regression flipping the default would silently
  promote every new member to owner (privilege-escalation)
- ``CustomerPortalCustomerUpdate.billing_name`` coerces empty
  strings to None — prevents a blank submission from overwriting
  an existing billing name with whitespace
- ``CustomerSelectionRequiredResponse.error`` is the fixed string
  ``"customer_selection_required"`` — the portal frontend
  dispatches on this exact value; drift would break the
  multi-customer disambiguation UI
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from rapidly.customers.customer_portal.types.customer import (
    CustomerPortalCustomerUpdate,
)
from rapidly.customers.customer_portal.types.customer_session import (
    CustomerSelectionRequiredResponse,
    CustomerSessionCodeAuthenticateRequest,
    CustomerSessionCodeRequest,
)
from rapidly.customers.customer_portal.types.member import (
    CustomerPortalMemberCreate,
    CustomerPortalMemberUpdate,
)
from rapidly.models.member import MemberRole


class TestCustomerPortalMemberCreate:
    def test_role_defaults_to_member(self) -> None:
        # Load-bearing privilege-escalation defence: the self-service
        # "invite teammate" path must default to the least-privileged
        # role. Flipping to ``owner`` would let any team-admin silently
        # escalate everyone they invite.
        body = CustomerPortalMemberCreate(email="new@test.com")
        assert body.role == MemberRole.member
        assert body.role.value != MemberRole.owner.value

    def test_requires_email(self) -> None:
        with pytest.raises(ValidationError):
            CustomerPortalMemberCreate.model_validate({})

    def test_rejects_invalid_email(self) -> None:
        with pytest.raises(ValidationError):
            CustomerPortalMemberCreate(email="not-an-email")

    def test_name_is_optional(self) -> None:
        body = CustomerPortalMemberCreate(email="new@test.com")
        assert body.name is None

    def test_explicit_role_is_respected(self) -> None:
        # When a team-admin explicitly chooses a non-default role
        # (e.g. billing_manager), the schema must honour it.
        body = CustomerPortalMemberCreate(
            email="new@test.com", role=MemberRole.billing_manager
        )
        assert body.role == MemberRole.billing_manager


class TestCustomerPortalMemberUpdate:
    def test_role_is_optional(self) -> None:
        body = CustomerPortalMemberUpdate()
        assert body.role is None

    def test_rejects_unknown_role(self) -> None:
        with pytest.raises(ValidationError):
            CustomerPortalMemberUpdate.model_validate({"role": "superadmin"})


class TestCustomerPortalCustomerUpdate:
    def test_billing_name_whitespace_coerces_to_none(self) -> None:
        # ``EmptyStrToNoneValidator`` on billing_name — a blank
        # submission must not overwrite the persisted name with
        # whitespace (would break invoice rendering).
        body = CustomerPortalCustomerUpdate(billing_name="   ")
        assert body.billing_name is None

    def test_billing_name_empty_coerces_to_none(self) -> None:
        body = CustomerPortalCustomerUpdate(billing_name="")
        assert body.billing_name is None

    def test_valid_billing_name_preserved(self) -> None:
        body = CustomerPortalCustomerUpdate(billing_name="Acme Inc")
        assert body.billing_name == "Acme Inc"

    def test_all_fields_optional(self) -> None:
        body = CustomerPortalCustomerUpdate()
        assert body.billing_name is None
        assert body.billing_address is None


class TestCustomerSessionCodeRequest:
    def test_requires_email_and_workspace(self) -> None:
        with pytest.raises(ValidationError):
            CustomerSessionCodeRequest.model_validate({})
        with pytest.raises(ValidationError):
            CustomerSessionCodeRequest.model_validate({"email": "c@test.com"})
        with pytest.raises(ValidationError):
            CustomerSessionCodeRequest.model_validate({"workspace_id": str(uuid4())})

    def test_customer_id_is_optional(self) -> None:
        body = CustomerSessionCodeRequest(email="c@test.com", workspace_id=uuid4())
        assert body.customer_id is None


class TestCustomerSessionCodeAuthenticateRequest:
    def test_requires_code(self) -> None:
        with pytest.raises(ValidationError):
            CustomerSessionCodeAuthenticateRequest.model_validate({})

    def test_accepts_code(self) -> None:
        body = CustomerSessionCodeAuthenticateRequest(code="123456")
        assert body.code == "123456"


class TestCustomerSelectionRequiredResponse:
    def test_error_literal_is_pinned(self) -> None:
        # The portal frontend dispatches on the exact string
        # ``"customer_selection_required"``. A rename here would
        # silently break the multi-customer disambiguation UI —
        # the frontend would land on the generic error screen
        # instead of the picker.
        body = CustomerSelectionRequiredResponse(customers=[])
        assert body.error == "customer_selection_required"

    def test_detail_has_user_facing_copy(self) -> None:
        # The ``detail`` field is the fallback when the frontend
        # doesn't yet know about the error code.
        body = CustomerSelectionRequiredResponse(customers=[])
        assert "select" in body.detail.lower()

    def test_customers_defaults_to_required(self) -> None:
        # A response WITHOUT customers is nonsensical (there's
        # nothing to select). Pinning the required-ness prevents
        # a regression that would let callers send an empty picker.
        # Note: empty list is technically valid, but ``customers``
        # itself must be present.
        with pytest.raises(ValidationError):
            CustomerSelectionRequiredResponse.model_validate({})
