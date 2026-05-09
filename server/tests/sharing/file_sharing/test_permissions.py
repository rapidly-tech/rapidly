"""Tests for ``rapidly/sharing/file_sharing/permissions.py``.

Pins the scope + subject sets on file-sharing endpoints.
Note the asymmetry: ``FileSharingRead`` accepts ``{User, Workspace}``
(either a human or a workspace access token can list sessions),
``FileSharingWrite`` accepts only ``{User}`` — workspace tokens
can't create new shares.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope
from rapidly.sharing.file_sharing import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestFileSharingRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.FileSharingRead).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes(self) -> None:
        assert _extract(perms.FileSharingRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.file_sharing_read,
        }


class TestFileSharingWrite:
    def test_allows_only_user_not_workspace(self) -> None:
        # Key asymmetry: workspace access tokens cannot create shares.
        # Share creation is a user-attribution-required action.
        assert _extract(perms.FileSharingWrite).allowed_subjects == {User}

    def test_required_scopes_are_write_only(self) -> None:
        assert _extract(perms.FileSharingWrite).required_scopes == {
            Scope.web_write,
            Scope.file_sharing_write,
        }

    def test_does_not_accept_read_only_scopes(self) -> None:
        required = _extract(perms.FileSharingWrite).required_scopes or set()
        assert Scope.file_sharing_read not in required
        assert Scope.web_read not in required
