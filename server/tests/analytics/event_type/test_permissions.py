"""Tests for ``rapidly/analytics/event_type/permissions.py``.

Pins scopes + allowed subjects for event-type routes. Note the
asymmetry: EventTypeRead requires any events_* scope; EventTypeWrite
requires ONLY web:write (no dedicated event_types_write scope — all
event-type mutations happen from the dashboard web session).
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.analytics.event_type import permissions as perms
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


class TestEventTypeRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.EventTypeRead).allowed_subjects == {User, Workspace}

    def test_scopes_match_events_read_family(self) -> None:
        assert _extract(perms.EventTypeRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.events_read,
            Scope.events_write,
        }


class TestEventTypeWrite:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.EventTypeWrite).allowed_subjects == {User, Workspace}

    def test_requires_only_web_write(self) -> None:
        # Event-type mutations are a dashboard-only capability — no
        # public OAuth scope exists for them. Pinned to web:write
        # exclusively.
        auth = _extract(perms.EventTypeWrite)
        assert auth.required_scopes == {Scope.web_write}

    def test_does_not_require_events_write(self) -> None:
        # Asymmetric with EventTypeRead — write doesn't require the
        # events_* scope family. Pinned explicitly.
        auth = _extract(perms.EventTypeWrite)
        required = auth.required_scopes or set()
        assert Scope.events_write not in required
