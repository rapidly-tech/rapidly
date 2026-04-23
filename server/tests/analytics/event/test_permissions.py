"""Tests for ``rapidly/analytics/event/permissions.py``.

Pins the scope sets + allowed subjects on event endpoints.
Security-critical: any silent widening of scopes or subjects opens
the endpoint beyond its documented audience.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.analytics.event import permissions as perms
from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope


def _extract_authenticator(annotated_type: object) -> _Authenticator:
    # Annotated[AuthPrincipal[...], Depends(_Authenticator(...))] — pull
    # the Depends metadata out so we can inspect the Authenticator.
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestEventRead:
    def test_allows_user_and_workspace_subjects(self) -> None:
        auth = _extract_authenticator(perms.EventRead)
        assert auth.allowed_subjects == {User, Workspace}

    def test_required_scopes_include_events_read_plus_web(self) -> None:
        auth = _extract_authenticator(perms.EventRead)
        assert auth.required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.events_read,
            Scope.events_write,
        }

    def test_does_not_include_unrelated_scopes(self) -> None:
        # Explicit "this isn't a write-anywhere token" guard.
        auth = _extract_authenticator(perms.EventRead)
        required = auth.required_scopes or set()
        for forbidden in (
            Scope.file_sharing_write,
            Scope.customers_write,
            Scope.webhooks_write,
        ):
            assert forbidden not in required


class TestEventWrite:
    def test_allows_user_and_workspace_subjects(self) -> None:
        auth = _extract_authenticator(perms.EventWrite)
        assert auth.allowed_subjects == {User, Workspace}

    def test_requires_events_write_and_web_write_only(self) -> None:
        # Narrower than Read — write endpoints must NOT accept read-only
        # tokens.
        auth = _extract_authenticator(perms.EventWrite)
        assert auth.required_scopes == {Scope.web_write, Scope.events_write}

    def test_read_only_scopes_reject_the_write_guard(self) -> None:
        # A token with only ``events_read`` must fail the write guard's
        # scope-intersection check. Pinned by asserting ``events_read``
        # is NOT in the required set.
        auth = _extract_authenticator(perms.EventWrite)
        required = auth.required_scopes or set()
        assert Scope.events_read not in required
        assert Scope.web_read not in required
