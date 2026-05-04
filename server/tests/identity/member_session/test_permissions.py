"""Tests for ``rapidly/identity/member_session/permissions.py``.

Pins the scope + subject set on the member-session-create endpoint.
Member sessions are how a workspace operator impersonates a member
for support purposes; the endpoint MUST reject any token that
doesn't hold ``member_sessions:write``.
"""

from __future__ import annotations

from fastapi.params import Depends

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.models import User, Workspace
from rapidly.identity.auth.scope import Scope
from rapidly.identity.member_session import permissions as perms


def _extract(annotated_type: object) -> _Authenticator:
    meta = annotated_type.__metadata__  # type: ignore[attr-defined]
    dep = meta[0]
    assert isinstance(dep, Depends)
    auth = dep.dependency
    assert isinstance(auth, _Authenticator)
    return auth


class TestMemberSessionWrite:
    def test_allows_user_and_workspace(self) -> None:
        assert _extract(perms.MemberSessionWrite).allowed_subjects == {
            User,
            Workspace,
        }

    def test_required_scopes(self) -> None:
        # The dedicated ``member_sessions:write`` scope — distinct
        # from ``members:write`` — gates impersonation-style actions.
        assert _extract(perms.MemberSessionWrite).required_scopes == {
            Scope.web_write,
            Scope.member_sessions_write,
        }

    def test_does_not_accept_members_write_as_substitute(self) -> None:
        # members:write creates / updates member records; it does NOT
        # grant the right to mint sessions on their behalf. Pinning
        # the split catches a refactor that collapses the two scopes.
        required = _extract(perms.MemberSessionWrite).required_scopes or set()
        assert Scope.members_write not in required

    def test_module_does_not_export_MemberSessionRead(self) -> None:
        # Session tokens are ephemeral; reading back a list of member
        # sessions is not a documented capability. Pinning so a
        # refactor that adds one would require security review.
        assert not hasattr(perms, "MemberSessionRead")
