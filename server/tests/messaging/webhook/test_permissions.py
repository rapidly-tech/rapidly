"""Tests for ``rapidly/messaging/webhook/permissions.py``.

Pins scope + subject sets on webhook management routes. Webhooks are
a workspace-scoped resource (distinct from user-owned notification
preferences) — both Read and Write accept ``{User, Workspace}``.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope
from rapidly.messaging.webhook import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestWebhooksRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.WebhooksRead).allowed_subjects == {User, Workspace}

    def test_required_scopes(self) -> None:
        assert _extract(perms.WebhooksRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.webhooks_read,
            Scope.webhooks_write,
        }


class TestWebhooksWrite:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.WebhooksWrite).allowed_subjects == {User, Workspace}

    def test_required_scopes_are_write_only(self) -> None:
        assert _extract(perms.WebhooksWrite).required_scopes == {
            Scope.web_write,
            Scope.webhooks_write,
        }

    def test_does_not_accept_read_only_scopes(self) -> None:
        required = _extract(perms.WebhooksWrite).required_scopes or set()
        assert Scope.webhooks_read not in required
        assert Scope.web_read not in required
