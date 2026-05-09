"""Tests for ``rapidly/enums.py``.

Shared domain enums. Several have load-bearing wire values:

- ``TokenType`` values are the **secret-scanning identifiers** that
  GitHub (and similar services) pattern-match on to detect leaked
  tokens. Every value must start with ``rapidly_`` so the upstream
  secret-scanning allow-list catches them. Drift would surface as
  unflagged leaks on public repos.
- ``AccountType`` / ``PaymentProcessor`` wire values flow into
  billing records; drift would desync the dashboard filters from
  the DB column.
- ``RateLimitGroup`` — the middleware dispatches on these; adding
  a group silently without wiring a bucket breaks rate-limit
  decisioning.
"""

from __future__ import annotations

import pytest

from rapidly.enums import AccountType, PaymentProcessor, RateLimitGroup, TokenType


class TestPaymentProcessor:
    def test_stripe_is_the_only_processor(self) -> None:
        # Pinning the single processor — adding Paddle / LemonSqueezy
        # here without wiring the rest of the billing pipeline would
        # break every checkout referencing the new value.
        assert {e.value for e in PaymentProcessor} == {"stripe"}


class TestAccountType:
    def test_values_match_wire_strings(self) -> None:
        assert {e.value for e in AccountType} == {"stripe", "manual"}

    def test_display_names_cover_every_value(self) -> None:
        # ``get_display_name`` must answer for every enum member —
        # a new AccountType without a dictionary entry would
        # KeyError the dashboard's account-list renderer.
        for member in AccountType:
            # The method indexes into a dict keyed by enum members.
            # Any member without an entry raises KeyError here.
            display = member.get_display_name()
            assert isinstance(display, str)
            assert len(display) > 0

    def test_specific_display_names(self) -> None:
        assert AccountType.stripe.get_display_name() == "Stripe Connect Express"
        assert AccountType.manual.get_display_name() == "Manual"


class TestTokenType:
    @pytest.mark.parametrize(
        ("attr", "wire_value"),
        [
            ("client_secret", "rapidly_client_secret"),
            ("client_registration_token", "rapidly_client_registration_token"),
            ("authorization_code", "rapidly_authorization_code"),
            ("access_token", "rapidly_access_token"),
            ("refresh_token", "rapidly_refresh_token"),
            ("personal_access_token", "rapidly_personal_access_token"),
            ("workspace_access_token", "rapidly_workspace_access_token"),
            ("customer_session_token", "rapidly_customer_session_token"),
            ("user_session_token", "rapidly_user_session_token"),
        ],
    )
    def test_every_wire_value_pinned(self, attr: str, wire_value: str) -> None:
        # Load-bearing security pin. GitHub's secret-scanning partner
        # registry matches these exact strings; a silent rename would
        # mean leaked tokens stop getting flagged on public repos.
        assert getattr(TokenType, attr).value == wire_value

    def test_every_value_has_rapidly_prefix(self) -> None:
        # Belt-and-suspenders: beyond the explicit per-value pin,
        # no value may drop the ``rapidly_`` prefix.
        for member in TokenType:
            assert member.value.startswith("rapidly_")

    def test_enum_has_exactly_nine_members(self) -> None:
        # Arity pin — adding a token type without wiring the secret-
        # scanning registry is a silent leak surface.
        assert len(list(TokenType)) == 9

    def test_personal_access_token_retained_for_compat(self) -> None:
        # Deprecated but kept for secret-scanning compat. Removing
        # would stop flagging leaked legacy tokens still in the
        # wild.
        assert TokenType.personal_access_token.value == "rapidly_personal_access_token"


class TestRateLimitGroup:
    def test_covers_expected_groups(self) -> None:
        # The auth-middleware dispatches on these; adding a value
        # without wiring a bucket breaks rate-limit decisioning.
        assert {e.value for e in RateLimitGroup} == {
            "web",
            "restricted",
            "default",
            "elevated",
        }
