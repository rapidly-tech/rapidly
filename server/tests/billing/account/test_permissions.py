"""Tests for ``rapidly/billing/account/permissions.py``.

Pins the scope + subject set on billing-account routes. These routes
manage the Stripe Connect account owned by a single user (platform
operator's payout destination), so both Read and Write are restricted
to ``{User}`` — workspace access tokens cannot enrol a new payout
destination on the operator's behalf.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.billing.account import permissions as perms
from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User
from rapidly.identity.auth.scope import Scope


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestAccountRead:
    def test_allows_only_User_not_Workspace(self) -> None:
        # Key asymmetry: workspace access tokens cannot read the
        # operator's Stripe-account wiring. Pinned so a refactor that
        # widens the subject set would require an explicit payout-
        # security review.
        assert _extract(perms.AccountRead).allowed_subjects == {User}

    def test_required_scopes_are_web_only(self) -> None:
        # No dedicated billing_account:read scope — session-only.
        assert _extract(perms.AccountRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
        }


class TestAccountWrite:
    def test_allows_only_User_not_Workspace(self) -> None:
        # Same user-only restriction as Read — mutations to the
        # payout destination are an operator-only action.
        assert _extract(perms.AccountWrite).allowed_subjects == {User}

    def test_required_scopes_are_web_write_only(self) -> None:
        assert _extract(perms.AccountWrite).required_scopes == {Scope.web_write}

    def test_does_not_accept_web_read_only_tokens(self) -> None:
        required = _extract(perms.AccountWrite).required_scopes or set()
        assert Scope.web_read not in required
