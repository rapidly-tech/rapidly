"""Tests for ``rapidly/platform/user/permissions.py``.

Pins the scope + subject set on user-account routes. UserWrite is
the gate for account deletion (``user:write`` scope); UserScopesRead
is the "what scopes does my token have" introspection endpoint —
which requires NO scopes, only authentication.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User
from rapidly.identity.auth.scope import Scope
from rapidly.platform.user import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestUserWrite:
    def test_allows_only_User(self) -> None:
        # User-account mutations (delete account) are strictly a
        # user-owned action. Workspace tokens cannot delete users.
        assert _extract(perms.UserWrite).allowed_subjects == {User}

    def test_required_scopes(self) -> None:
        assert _extract(perms.UserWrite).required_scopes == {
            Scope.web_write,
            Scope.user_write,
        }


class TestUserScopesRead:
    def test_allows_only_User(self) -> None:
        assert _extract(perms.UserScopesRead).allowed_subjects == {User}

    def test_has_no_required_scopes(self) -> None:
        # Introspection endpoint: requires a valid user session but
        # not any particular scope. Pinned because the Authenticator
        # default for ``required_scopes`` should be None/empty — a
        # refactor that swapped the default to "web_read" would
        # silently block unscoped sessions from introspection.
        auth = _extract(perms.UserScopesRead)
        assert not auth.required_scopes

    def test_module_does_not_export_UserRead(self) -> None:
        # The user's own profile is fetched via a different endpoint
        # (via the session directly, not a scoped API). Pinning so
        # an added UserRead would be a deliberate, reviewed change.
        assert not hasattr(perms, "UserRead")
