"""Tests for ``rapidly/messaging/notification_recipient/permissions.py``.

Pins scope + subject sets on notification-recipient routes. Both Read
and Write restrict to ``{User}`` — recipients are tied to a human
operator's notification preferences, so workspace automation tokens
must not modify them.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope
from rapidly.messaging.notification_recipient import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestNotificationRecipientRead:
    def test_allows_only_User_not_Workspace(self) -> None:
        # Recipient records store user-identifying preferences —
        # workspace tokens have no legitimate reason to read them.
        auth = _extract(perms.NotificationRecipientRead)
        assert auth.allowed_subjects == {User}
        assert Workspace not in auth.allowed_subjects

    def test_required_scopes(self) -> None:
        assert _extract(perms.NotificationRecipientRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.notification_recipients_read,
            Scope.notification_recipients_write,
        }


class TestNotificationRecipientWrite:
    def test_allows_only_User_not_Workspace(self) -> None:
        auth = _extract(perms.NotificationRecipientWrite)
        assert auth.allowed_subjects == {User}

    def test_required_scopes_are_write_only(self) -> None:
        assert _extract(perms.NotificationRecipientWrite).required_scopes == {
            Scope.web_write,
            Scope.notification_recipients_write,
        }

    def test_does_not_accept_read_only_scopes(self) -> None:
        required = _extract(perms.NotificationRecipientWrite).required_scopes or set()
        assert Scope.notification_recipients_read not in required
        assert Scope.web_read not in required
