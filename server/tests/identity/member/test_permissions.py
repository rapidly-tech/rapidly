"""Tests for ``rapidly/identity/member/permissions.py``.

Pins the scope + subject sets on member-management endpoints.
Cross-tenant auth-bypass prevention: write endpoints must reject
read-only tokens.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope
from rapidly.identity.member import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestMemberRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.MemberRead).allowed_subjects == {User, Workspace}

    def test_required_scopes(self) -> None:
        assert _extract(perms.MemberRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.members_read,
            Scope.members_write,
        }


class TestMemberWrite:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.MemberWrite).allowed_subjects == {User, Workspace}

    def test_required_scopes_are_write_only(self) -> None:
        # Narrower than MemberRead — read-only tokens must be rejected.
        assert _extract(perms.MemberWrite).required_scopes == {
            Scope.web_write,
            Scope.members_write,
        }

    def test_does_not_accept_read_only_scopes(self) -> None:
        required = _extract(perms.MemberWrite).required_scopes or set()
        assert Scope.members_read not in required
        assert Scope.web_read not in required
