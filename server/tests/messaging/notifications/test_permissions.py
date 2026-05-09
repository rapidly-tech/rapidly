"""Tests for ``rapidly/messaging/notifications/permissions.py``.

Pins scope + subject sets on notification routes (user-facing
dashboard notifications). User-only — a workspace automation token
has no legitimate reason to read/mark a human user's notifications.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope
from rapidly.messaging.notifications import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestNotificationsRead:
    def test_allows_only_User_not_Workspace(self) -> None:
        auth = _extract(perms.NotificationsRead)
        assert auth.allowed_subjects == {User}
        assert Workspace not in auth.allowed_subjects

    def test_required_scopes(self) -> None:
        assert _extract(perms.NotificationsRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.notifications_read,
        }


class TestNotificationsWrite:
    def test_allows_only_User(self) -> None:
        assert _extract(perms.NotificationsWrite).allowed_subjects == {User}

    def test_required_scopes_are_write_only(self) -> None:
        assert _extract(perms.NotificationsWrite).required_scopes == {
            Scope.web_write,
            Scope.notifications_write,
        }

    def test_does_not_accept_read_only_scopes(self) -> None:
        required = _extract(perms.NotificationsWrite).required_scopes or set()
        assert Scope.notifications_read not in required
        assert Scope.web_read not in required
