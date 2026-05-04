"""Tests for ``rapidly/billing/stripe_connect/permissions.py``.

Pins the scope + subject set on Stripe Connect routes. These routes
return configuration + connect-onboarding links, all read-only from
our perspective (Stripe is the source of truth for payout state).
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.billing.stripe_connect import permissions as perms
from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestStripeConnectRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.StripeConnectRead).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes_are_web_only(self) -> None:
        # No dedicated ``stripe_connect:read`` scope — the route is
        # gated by session-only presence (web_read/web_write).
        assert _extract(perms.StripeConnectRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
        }

    def test_module_does_not_export_StripeConnectWrite(self) -> None:
        # Stripe Connect state lives in Stripe; we don't mutate it
        # server-side. Pinning prevents accidental addition of a write
        # variant without explicit security review.
        assert not hasattr(perms, "StripeConnectWrite")
