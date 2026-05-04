"""Tests for ``rapidly/billing/payment/permissions.py``.

Pins the scope + subject set on payment listing endpoints. Payments
are read-only from the API's perspective — Stripe webhooks write
the state, the API surface exposes read access.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.billing.payment import permissions as perms
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


class TestPaymentRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.PaymentRead).allowed_subjects == {User, Workspace}

    def test_required_scopes(self) -> None:
        assert _extract(perms.PaymentRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.payments_read,
        }

    def test_module_does_not_export_PaymentWrite(self) -> None:
        # Payment state is write-through-Stripe-webhooks only.
        # Pinning prevents a refactor that lets API callers mutate
        # payment records directly (would break reconciliation).
        assert not hasattr(perms, "PaymentWrite")
