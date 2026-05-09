"""Tests for ``rapidly/catalog/file/permissions.py``.

Pins the scope + subject sets on catalog file endpoints.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.catalog.file import permissions as perms
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


class TestFileRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.FileRead).allowed_subjects == {User, Workspace}

    def test_required_scopes(self) -> None:
        assert _extract(perms.FileRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.files_read,
            Scope.files_write,
        }


class TestFileWrite:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.FileWrite).allowed_subjects == {User, Workspace}

    def test_required_scopes_are_write_only(self) -> None:
        assert _extract(perms.FileWrite).required_scopes == {
            Scope.web_write,
            Scope.files_write,
        }

    def test_does_not_accept_read_only_scopes(self) -> None:
        required = _extract(perms.FileWrite).required_scopes or set()
        assert Scope.files_read not in required
        assert Scope.web_read not in required
