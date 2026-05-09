"""Tests for ``rapidly/catalog/custom_field/permissions.py``.

Pins the scope + subject sets on custom-field endpoints.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.catalog.custom_field import permissions as perms
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


class TestCustomFieldRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.CustomFieldRead).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes(self) -> None:
        assert _extract(perms.CustomFieldRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.custom_fields_read,
            Scope.custom_fields_write,
        }


class TestCustomFieldWrite:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.CustomFieldWrite).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes_are_write_only(self) -> None:
        assert _extract(perms.CustomFieldWrite).required_scopes == {
            Scope.web_write,
            Scope.custom_fields_write,
        }

    def test_does_not_accept_read_only_scopes(self) -> None:
        required = _extract(perms.CustomFieldWrite).required_scopes or set()
        assert Scope.custom_fields_read not in required
        assert Scope.web_read not in required
