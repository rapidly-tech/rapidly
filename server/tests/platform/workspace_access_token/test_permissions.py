"""Tests for ``rapidly/platform/workspace_access_token/permissions.py``.

Pins the scope + subject set on workspace-access-token CRUD. These
are the tokens that automation uses to act as a workspace; mis-
scoping lets any token mint new workspace tokens (an auth-escalation
primitive).
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope
from rapidly.platform.workspace_access_token import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestWorkspaceAccessTokensRead:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.WorkspaceAccessTokensRead).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes(self) -> None:
        assert _extract(perms.WorkspaceAccessTokensRead).required_scopes == {
            Scope.web_read,
            Scope.web_write,
            Scope.workspace_access_tokens_read,
            Scope.workspace_access_tokens_write,
        }


class TestWorkspaceAccessTokensWrite:
    def test_allows_user_and_workspace(self) -> None:
        # Workspace can mint child tokens — this is intentional for
        # automation-flows (e.g. a platform admin token bootstraps a
        # workspace with its own narrower tokens).
        assert _extract(perms.WorkspaceAccessTokensWrite).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes_are_write_only(self) -> None:
        assert _extract(perms.WorkspaceAccessTokensWrite).required_scopes == {
            Scope.web_write,
            Scope.workspace_access_tokens_write,
        }

    def test_does_not_accept_read_only_scopes(self) -> None:
        required = _extract(perms.WorkspaceAccessTokensWrite).required_scopes or set()
        # Critical: a token holding only workspace_access_tokens_read
        # must NOT be able to mint new tokens (would be a privilege-
        # escalation primitive).
        assert Scope.workspace_access_tokens_read not in required
        assert Scope.web_read not in required
