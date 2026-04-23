"""Tests for ``rapidly/customers/customer_portal/permissions.py``.

Customer-portal is the most structurally complex permissions module
in the codebase — 10 exported auth dependencies covering three
subject kinds (Customer / Member / Anonymous), three scope variants
(read / write / OAuth-account), and two role-gated billing flows.

Tests split into:
- Customer-only (legacy pre-migration)
- Member-only (for orgs with member_model_enabled)
- Union (accept either Customer or Member)
- OAuth-account (Customer | Member | Anonymous — lowest-bar pre-auth)
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.customers.customer_portal import permissions as perms
from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import Anonymous, Customer, Member
from rapidly.identity.auth.scope import Scope


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


# ── Customer-only (legacy) ────────────────────────────────────────────


class TestCustomerPortalRead:
    def test_allows_only_Customer(self) -> None:
        assert _extract(perms.CustomerPortalRead).allowed_subjects == {Customer}

    def test_required_scopes(self) -> None:
        assert _extract(perms.CustomerPortalRead).required_scopes == {
            Scope.customer_portal_read,
            Scope.customer_portal_write,
        }


class TestCustomerPortalWrite:
    def test_allows_only_Customer(self) -> None:
        assert _extract(perms.CustomerPortalWrite).allowed_subjects == {Customer}

    def test_requires_write_scope_only(self) -> None:
        # Narrower than Read — write-only sessions accepted.
        assert _extract(perms.CustomerPortalWrite).required_scopes == {
            Scope.customer_portal_write,
        }


# ── OAuth-account (lowest-bar pre-auth flow) ──────────────────────────


class TestCustomerPortalOAuthAccount:
    def test_accepts_Customer_Member_and_Anonymous(self) -> None:
        # This is the pre-auth OAuth-account-link flow — Anonymous
        # must pass because the caller hasn't authenticated yet.
        assert _extract(perms.CustomerPortalOAuthAccount).allowed_subjects == {
            Customer,
            Member,
            Anonymous,
        }

    def test_requires_customer_portal_write_scope(self) -> None:
        assert _extract(perms.CustomerPortalOAuthAccount).required_scopes == {
            Scope.customer_portal_write,
        }


# ── Member-only (for member_model_enabled orgs) ───────────────────────


class TestCustomerPortalMemberRead:
    def test_allows_only_Member(self) -> None:
        # Customer-only orgs use CustomerPortalRead; Member orgs use
        # this variant. Pinning the split prevents a silent unification
        # that would either let a Customer through a Member-only guard
        # or block a Member on a Customer-only one.
        assert _extract(perms.CustomerPortalMemberRead).allowed_subjects == {Member}

    def test_required_scopes(self) -> None:
        assert _extract(perms.CustomerPortalMemberRead).required_scopes == {
            Scope.customer_portal_read,
            Scope.customer_portal_write,
        }


class TestCustomerPortalMemberWrite:
    def test_allows_only_Member(self) -> None:
        assert _extract(perms.CustomerPortalMemberWrite).allowed_subjects == {Member}

    def test_requires_write_scope(self) -> None:
        assert _extract(perms.CustomerPortalMemberWrite).required_scopes == {
            Scope.customer_portal_write,
        }


# ── Union (Customer | Member during migration) ────────────────────────


class TestCustomerPortalUnionRead:
    def test_accepts_Customer_and_Member(self) -> None:
        # The union variant is the migration path — endpoints can
        # opt into union for multi-org support without forcing every
        # org onto one side of the split.
        assert _extract(perms.CustomerPortalUnionRead).allowed_subjects == {
            Customer,
            Member,
        }

    def test_required_scopes(self) -> None:
        assert _extract(perms.CustomerPortalUnionRead).required_scopes == {
            Scope.customer_portal_read,
            Scope.customer_portal_write,
        }


class TestCustomerPortalUnionWrite:
    def test_accepts_Customer_and_Member(self) -> None:
        assert _extract(perms.CustomerPortalUnionWrite).allowed_subjects == {
            Customer,
            Member,
        }

    def test_requires_write_scope(self) -> None:
        assert _extract(perms.CustomerPortalUnionWrite).required_scopes == {
            Scope.customer_portal_write,
        }
