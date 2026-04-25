"""Tests for ``rapidly/admin/workspaces/forms.py``.

Admin moderation form schemas. Five load-bearing surfaces:

- ``WorkspaceStatusForm`` is a discriminated union over the
  documented FIVE action literals (``approve`` / ``deny`` /
  ``under_review`` / ``approve_appeal`` / ``deny_appeal``).
  Drift to drop a variant would break the corresponding admin
  button — submitting it would 422.
- ``ApproveWorkspaceForm.next_review_threshold`` is
  ``Annotated[int, Ge(0), ...]`` — drift would let moderators
  enter a NEGATIVE threshold and accidentally trigger immediate
  re-review on approve.
- ``UpdateWorkspaceBasicForm.customer_invoice_prefix`` is
  ``StringConstraints(to_upper=True, min_length=3, pattern=...)``.
  The pattern requires the LAST character be alphanumeric (not
  dash). Drift to drop the trailing-alphanumeric guard would let
  prefixes like ``"ABC-"`` end up on customer invoices.
- ``AddPaymentMethodDomainForm.domain_name`` is constrained to
  ``max_length=253`` (DNS label limit) with an RFC-1035 hostname
  regex. Drift would let arbitrary strings be sent to Apple Pay
  / Google Pay's allowlist API.
- ``DisconnectStripeAccountForm`` and ``DeleteStripeAccountForm``
  both require a non-empty ``reason``. Drift would lose the
  audit trail on Stripe account terminations.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.admin.workspaces.forms import (
    AddPaymentMethodDomainForm,
    ApproveWorkspaceAppealForm,
    ApproveWorkspaceForm,
    DeleteStripeAccountForm,
    DenyWorkspaceAppealForm,
    DenyWorkspaceForm,
    DisconnectStripeAccountForm,
    UnderReviewWorkspaceForm,
    UpdateWorkspaceBasicForm,
    WorkspaceStatusFormAdapter,
)


class TestStatusFormDiscriminator:
    def test_documented_five_action_literals(self) -> None:
        # Pin: the 5 actions wired to admin buttons. Drift to
        # drop one would 422 on submission.
        assert ApproveWorkspaceForm.model_fields["action"].annotation is not None
        # The discriminator parses each literal correctly via the
        # adapter.
        for action, payload in [
            ("approve", {"action": "approve", "next_review_threshold": 0}),
            ("deny", {"action": "deny"}),
            ("under_review", {"action": "under_review"}),
            ("approve_appeal", {"action": "approve_appeal"}),
            ("deny_appeal", {"action": "deny_appeal"}),
        ]:
            parsed = WorkspaceStatusFormAdapter.validate_python(payload)
            assert parsed.action == action

    def test_unknown_action_rejected(self) -> None:
        # Pin: the discriminator REJECTS unknown actions rather
        # than coercing — drift would silently allow new admin
        # buttons that have no corresponding handler.
        with pytest.raises(ValidationError):
            WorkspaceStatusFormAdapter.validate_python({"action": "ghost"})

    def test_status_variants_are_distinct_types(self) -> None:
        # Pin: each variant resolves to a distinct class so the
        # router can dispatch on isinstance.
        approve = WorkspaceStatusFormAdapter.validate_python(
            {"action": "approve", "next_review_threshold": 100}
        )
        deny = WorkspaceStatusFormAdapter.validate_python({"action": "deny"})
        under_review = WorkspaceStatusFormAdapter.validate_python(
            {"action": "under_review"}
        )
        approve_appeal = WorkspaceStatusFormAdapter.validate_python(
            {"action": "approve_appeal"}
        )
        deny_appeal = WorkspaceStatusFormAdapter.validate_python(
            {"action": "deny_appeal"}
        )
        assert isinstance(approve, ApproveWorkspaceForm)
        assert isinstance(deny, DenyWorkspaceForm)
        assert isinstance(under_review, UnderReviewWorkspaceForm)
        assert isinstance(approve_appeal, ApproveWorkspaceAppealForm)
        assert isinstance(deny_appeal, DenyWorkspaceAppealForm)


class TestApproveThresholdNonNegative:
    def test_zero_is_valid(self) -> None:
        # Pin: ``Ge(0)`` allows zero (admin may approve without
        # setting a future review).
        form = ApproveWorkspaceForm(action="approve", next_review_threshold=0)
        assert form.next_review_threshold == 0

    def test_positive_is_valid(self) -> None:
        # Pin: a positive integer is accepted by the ``Ge(0)``
        # constraint. (The CurrencyValidator scales the value
        # internally; we only pin the non-negativity guard here.)
        form = ApproveWorkspaceForm(action="approve", next_review_threshold=1000)
        assert form.next_review_threshold > 0

    def test_negative_threshold_rejected(self) -> None:
        # Pin: drift to allow negatives would either fire
        # immediate re-review on approve, or surface as a
        # confusing UI state where the "next review" date is in
        # the past.
        with pytest.raises(ValidationError):
            ApproveWorkspaceForm(action="approve", next_review_threshold=-1)


class TestInvoicePrefixConstraints:
    _BASE = {"name": "Acme", "slug": "acme"}

    def test_uppercases_lowercase_input(self) -> None:
        # Pin: ``to_upper=True`` normalises lower-case prefixes.
        # Drift would let lower-case prefixes leak onto invoices,
        # breaking visual scan-ability for accounting.
        form = UpdateWorkspaceBasicForm(**self._BASE, customer_invoice_prefix="abc")
        assert form.customer_invoice_prefix == "ABC"

    def test_short_prefix_rejected(self) -> None:
        # Pin: ``min_length=3`` to keep prefixes scan-able on
        # paper invoices.
        with pytest.raises(ValidationError):
            UpdateWorkspaceBasicForm(**self._BASE, customer_invoice_prefix="AB")

    def test_trailing_dash_rejected(self) -> None:
        # Pin: prefix MUST end on an alphanumeric character.
        # Drift to allow a trailing dash would render invoices
        # like "ABC--12345" which is confusing AND complicates
        # the downstream parser.
        with pytest.raises(ValidationError):
            UpdateWorkspaceBasicForm(**self._BASE, customer_invoice_prefix="ABC-")

    def test_internal_dash_allowed(self) -> None:
        # Pin: dashes ARE allowed in the middle. Drift to forbid
        # all dashes would block legitimate prefixes like
        # ``ABC-NL`` for regional sub-accounts.
        form = UpdateWorkspaceBasicForm(**self._BASE, customer_invoice_prefix="ABC-NL")
        assert form.customer_invoice_prefix == "ABC-NL"


class TestDomainNameConstraints:
    def test_valid_hostname_accepted(self) -> None:
        form = AddPaymentMethodDomainForm(domain_name="example.com")
        assert form.domain_name == "example.com"

    def test_subdomain_accepted(self) -> None:
        form = AddPaymentMethodDomainForm(domain_name="checkout.example.com")
        assert form.domain_name == "checkout.example.com"

    def test_url_with_scheme_rejected(self) -> None:
        # Pin: the regex requires bare hostnames. Drift to
        # accept "https://..." would send a junk value to Apple
        # Pay / Google Pay's allowlist API.
        with pytest.raises(ValidationError):
            AddPaymentMethodDomainForm(domain_name="https://example.com")

    def test_overlong_hostname_rejected(self) -> None:
        # Pin: max_length=253 (the RFC 1035 DNS limit). Drift
        # would let an overlong string be sent to the upstream
        # allowlist API and fail there.
        with pytest.raises(ValidationError):
            AddPaymentMethodDomainForm(domain_name="a" * 254 + ".com")


class TestStripeAccountReasonRequired:
    def test_disconnect_form_rejects_empty_reason(self) -> None:
        # Pin: audit trail. Drift to allow empty reason would
        # lose context on why a workspace's payment processor
        # was severed.
        with pytest.raises(ValidationError):
            DisconnectStripeAccountForm(stripe_account_id="acct_1", reason="")

    def test_delete_form_rejects_empty_reason(self) -> None:
        with pytest.raises(ValidationError):
            DeleteStripeAccountForm(stripe_account_id="acct_1", reason="")

    def test_disconnect_form_accepts_filled_reason(self) -> None:
        form = DisconnectStripeAccountForm(
            stripe_account_id="acct_1", reason="Fraud flag"
        )
        assert form.reason == "Fraud flag"
