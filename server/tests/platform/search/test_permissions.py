"""Tests for ``rapidly/platform/search/permissions.py``.

Pins the scope + subject set on the workspace-wide search endpoint.
Search indexes shares + customers, so the required scope set is the
union of both read/write families.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User
from rapidly.identity.auth.scope import Scope
from rapidly.platform.search import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestSearchRead:
    def test_allows_only_User(self) -> None:
        # Search is a dashboard feature; workspace access tokens have
        # no legitimate reason to fan out across all entities in the
        # workspace via a single endpoint.
        assert _extract(perms.SearchRead).allowed_subjects == {User}

    def test_requires_shares_and_customers_scopes(self) -> None:
        # Search aggregates shares + customers; any user with read
        # access to EITHER resource can search (Authenticator
        # requires at least one of the scopes — pinning the full set).
        assert _extract(perms.SearchRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.shares_read,
            Scope.shares_write,
            Scope.customers_read,
            Scope.customers_write,
        }

    def test_module_does_not_export_SearchWrite(self) -> None:
        # Search is a pure read path — pinned so a future refactor
        # adding a "save search" write endpoint doesn't silently land
        # without review.
        assert not hasattr(perms, "SearchWrite")
