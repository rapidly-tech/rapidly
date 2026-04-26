"""Tests for ``rapidly/billing/account/types.py``.

``AccountCreateForWorkspace`` is the onboarding entry point for
Stripe Connect. The country field is the gate for Stripe's
jurisdictional support — a silent drop from ``StripeAccountCountry``
would reject valid onboardings from that country; accepting a
country outside the enum would hand Stripe a code it rejects on
the backend call, 500ing the onboarding page.

Pins also:
- ``BeforeValidator(str.upper)`` on ``country`` — ``"us"`` lowercase
  must coerce to ``"US"``. A regression dropping this would fail
  every onboarding that hits the lowercase path (form-style input).
- ``account_type`` is ``Literal[AccountType.stripe]`` — no other
  account types currently supported
- ``AccountUpdate`` is fully partial
- ``AccountLink.url`` is a plain str (NOT HttpUrl) — Stripe-hosted
  onboarding URLs carry long signed tokens and don't always pass
  Pydantic's HttpUrl heuristics; tightening this would break
  onboarding
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from rapidly.billing.account.types import (
    AccountCreateForWorkspace,
    AccountLink,
    AccountUpdate,
    StripeAccountCountry,
)
from rapidly.enums import AccountType


class TestStripeAccountCountryCoverage:
    def test_includes_key_stripe_markets(self) -> None:
        # Spot-check: Stripe's largest-volume markets must be
        # present. A regression removing any of them would reject
        # onboardings from the majority of the user base.
        for code in ("US", "GB", "DE", "FR", "AU", "CA", "JP", "SG", "NL"):
            assert code in {e.value for e in StripeAccountCountry}

    def test_enum_has_expected_count(self) -> None:
        # 119 countries currently. Pinning the count prevents a
        # silent addition/removal that wasn't coordinated with the
        # OpenAPI docs or the onboarding copy.
        assert len(list(StripeAccountCountry)) == 119

    def test_all_values_are_iso_alpha2_uppercase(self) -> None:
        # ISO 3166-1 alpha-2 format: exactly two uppercase letters.
        # Drift (e.g. ``usa`` or ``us``) would break the Stripe API
        # call downstream.
        for e in StripeAccountCountry:
            assert len(e.value) == 2
            assert e.value.isupper()


class TestCountryNormalisation:
    def test_lowercase_coerces_to_uppercase(self) -> None:
        # ``BeforeValidator(str.upper)`` — a form submission with
        # ``"us"`` (lowercase) must round-trip to ``StripeAccountCountry.US``.
        body = AccountCreateForWorkspace(
            workspace_id=uuid4(),
            account_type=AccountType.stripe,
            country="us",  # type: ignore[arg-type]
        )
        assert body.country == StripeAccountCountry.US

    def test_mixed_case_coerces(self) -> None:
        body = AccountCreateForWorkspace(
            workspace_id=uuid4(),
            account_type=AccountType.stripe,
            country="Gb",  # type: ignore[arg-type]
        )
        assert body.country == StripeAccountCountry.GB

    def test_unknown_country_is_rejected(self) -> None:
        # ``XX`` is not in ISO or Stripe's list. Accepting it would
        # hand Stripe a code it rejects on the backend call.
        with pytest.raises(ValidationError):
            AccountCreateForWorkspace.model_validate(
                {
                    "workspace_id": str(uuid4()),
                    "account_type": AccountType.stripe.value,
                    "country": "XX",
                }
            )


class TestAccountCreateForWorkspace:
    def test_requires_workspace_id(self) -> None:
        with pytest.raises(ValidationError):
            AccountCreateForWorkspace.model_validate(
                {"account_type": AccountType.stripe.value, "country": "US"}
            )

    def test_requires_country(self) -> None:
        with pytest.raises(ValidationError):
            AccountCreateForWorkspace.model_validate(
                {
                    "workspace_id": str(uuid4()),
                    "account_type": AccountType.stripe.value,
                }
            )

    def test_account_type_is_literal_stripe(self) -> None:
        # Only ``stripe`` currently supported. A caller passing a
        # future/unsupported value must fail at validation, not
        # reach the Stripe Connect client which would error ambiguously.
        with pytest.raises(ValidationError):
            AccountCreateForWorkspace.model_validate(
                {
                    "workspace_id": str(uuid4()),
                    "account_type": "paddle",
                    "country": "US",
                }
            )


class TestAccountUpdateIsPartial:
    def test_all_fields_optional(self) -> None:
        body = AccountUpdate()
        assert body.billing_name is None
        assert body.billing_address is None
        assert body.billing_additional_info is None
        assert body.billing_notes is None


class TestAccountLinkPlainString:
    def test_url_is_a_plain_string_not_httpurl(self) -> None:
        # Stripe-hosted URLs carry long signed tokens (``?state=...``)
        # and don't always pass Pydantic's ``HttpUrl`` heuristics.
        # Pinning the field as a plain str prevents a well-intentioned
        # tightening that would break onboarding at the API boundary.
        link = AccountLink(url="https://connect.stripe.com/setup/s/acct_xyz?state=abc")
        assert link.url == "https://connect.stripe.com/setup/s/acct_xyz?state=abc"

        from pydantic.fields import FieldInfo

        field: FieldInfo = AccountLink.model_fields["url"]
        # ``str`` — NOT ``HttpUrl``. A regression to HttpUrl would
        # reject the trailing query params on some Stripe URLs.
        assert field.annotation is str
