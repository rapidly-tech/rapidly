"""Tests for ``rapidly/customers/customer_session/permissions.py``.

Mirrors member_session: a customer session is the impersonation /
ephemeral-token primitive for customer portal access.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.customers.customer_session import permissions as perms
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


class TestCustomerSessionWrite:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.CustomerSessionWrite).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes(self) -> None:
        assert _extract(perms.CustomerSessionWrite).required_scopes == {
            Scope.web_write,
            Scope.customer_sessions_write,
        }

    def test_does_not_accept_customers_write_as_substitute(self) -> None:
        # customers:write edits customer records; it does NOT grant
        # the right to mint sessions on their behalf. Pinning prevents
        # a refactor that collapses the two scopes.
        required = _extract(perms.CustomerSessionWrite).required_scopes or set()
        assert Scope.customers_write not in required

    def test_module_does_not_export_CustomerSessionRead(self) -> None:
        # Same rationale as member_session — session tokens are
        # ephemeral; listing them is not a documented capability.
        assert not hasattr(perms, "CustomerSessionRead")
