"""Tests for ``rapidly/platform/workspace/permissions.py``.

Five workspace auth dependencies with subtle subject-set differences:
- ``WorkspacesRead`` + ``WorkspacesWrite``: ``{User, Workspace}`` —
  workspace tokens can read/update their own record
- ``WorkspacesCreate``: ``{User}`` only — new workspaces need a
  human owner
- ``WorkspacesWriteUser``: ``{User}`` only — operator-only mutations
  (billing settings, etc.)
- ``WorkspacesReadOrAnonymous``: ``{User, Workspace, Anonymous}`` +
  NO scopes required — public storefront page access

Silent drift in these subject sets would either lock legitimate
workspaces out (false negatives) or let Anonymous callers act on
workspace state (authorisation bypass).
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import Anonymous, User, Workspace
from rapidly.identity.auth.scope import Scope
from rapidly.platform.workspace import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestWorkspacesRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.WorkspacesRead).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes(self) -> None:
        assert _extract(perms.WorkspacesRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.workspaces_read,
            Scope.workspaces_write,
        }


class TestWorkspacesWrite:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.WorkspacesWrite).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes(self) -> None:
        assert _extract(perms.WorkspacesWrite).required_scopes == {
            Scope.web_write,
            Scope.workspaces_write,
        }


class TestWorkspacesCreate:
    def test_allows_only_User_not_Workspace(self) -> None:
        # New workspaces need a human owner. Preventing workspace
        # tokens from creating child workspaces means the ownership
        # graph stays rooted at a user.
        assert _extract(perms.WorkspacesCreate).allowed_subjects == {User}

    def test_required_scopes(self) -> None:
        assert _extract(perms.WorkspacesCreate).required_scopes == {
            Scope.web_write,
            Scope.workspaces_write,
        }


class TestWorkspacesWriteUser:
    def test_allows_only_User_not_Workspace(self) -> None:
        # Operator-only mutations (billing settings, payout wiring).
        # Workspace tokens must not perform these.
        assert _extract(perms.WorkspacesWriteUser).allowed_subjects == {User}

    def test_required_scopes(self) -> None:
        assert _extract(perms.WorkspacesWriteUser).required_scopes == {
            Scope.web_write,
            Scope.workspaces_write,
        }


class TestWorkspacesReadOrAnonymous:
    def test_allows_user_workspace_and_anonymous(self) -> None:
        # Public storefront pages — Anonymous callers must pass.
        assert _extract(perms.WorkspacesReadOrAnonymous).allowed_subjects == {
            User,
            Workspace,
            Anonymous,
        }

    def test_requires_no_scopes(self) -> None:
        # Anonymous callers have no scopes; pinning empty set so a
        # refactor that adds any required scope silently blocks
        # anonymous access to storefronts.
        auth = _extract(perms.WorkspacesReadOrAnonymous)
        assert auth.required_scopes == set()
