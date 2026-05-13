"""Tests for ``rapidly.projects.project.access.require_role``.

This is the project-level authorisation gate.  Workspace membership
controls *visibility* of a project; this helper controls who can
*mutate* it.  Drift in any of these guarantees is a privilege-
escalation bug inside a workspace:

- Workspace-scoped tokens get implicit admin on every project in
  their own workspace — and only their own workspace.
- User principals must hold a ProjectMember role at-or-above the
  ``minimum`` floor.
- Missing membership rejects (not "treats as guest").
- Soft-deleted memberships are ignored (treated as not a member).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from rapidly.errors import NotPermitted
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    Project,
    ProjectMemberRole,
    User,
    Workspace,
)
from rapidly.projects.project import access


def _user_principal(user_id: UUID | None = None) -> AuthPrincipal[User]:
    user = User(id=user_id or uuid4(), email="dev@example.com")
    return AuthPrincipal(subject=user, scopes=set(), session=None)


def _workspace_principal(workspace_id: UUID | None = None) -> AuthPrincipal[Workspace]:
    workspace = Workspace(id=workspace_id or uuid4(), name="acme", slug="acme")
    return AuthPrincipal(subject=workspace, scopes=set(), session=None)


def _project(workspace_id: UUID | None = None) -> Project:
    project = Project(
        id=uuid4(),
        workspace_id=workspace_id or uuid4(),
        owner_id=uuid4(),
        name="P",
        identifier="P",
        slug="p",
    )
    return project


@pytest.mark.asyncio
class TestRequireRoleWorkspaceToken:
    async def test_workspace_token_in_same_workspace_passes(self) -> None:
        # Pin: workspace tokens are implicit project admins for every
        # project in their own workspace.  Drift would lock service
        # tokens out of write operations they should own.
        workspace_id = uuid4()
        principal = _workspace_principal(workspace_id)
        project = _project(workspace_id)

        # No DB session call should be made.
        session = MagicMock()
        session.execute = AsyncMock()

        await access.require_role(
            session, principal, project, minimum=ProjectMemberRole.admin
        )
        session.execute.assert_not_called()

    async def test_workspace_token_in_other_workspace_rejected(self) -> None:
        # Pin: workspace tokens MUST NOT cross workspace boundaries
        # even if they somehow obtain a Project reference.  Drift
        # is a tenant-isolation break.
        principal = _workspace_principal(uuid4())
        project = _project(uuid4())  # different workspace
        session = MagicMock()

        with pytest.raises(NotPermitted):
            await access.require_role(
                session, principal, project, minimum=ProjectMemberRole.member
            )


@pytest.mark.asyncio
class TestRequireRoleUserPrincipal:
    async def test_non_member_rejected(self) -> None:
        principal = _user_principal()
        project = _project()

        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        with pytest.raises(NotPermitted):
            await access.require_role(
                session, principal, project, minimum=ProjectMemberRole.guest
            )

    @pytest.mark.parametrize(
        ("member_role", "minimum", "should_pass"),
        [
            (ProjectMemberRole.guest, ProjectMemberRole.guest, True),
            (ProjectMemberRole.guest, ProjectMemberRole.member, False),
            (ProjectMemberRole.guest, ProjectMemberRole.admin, False),
            (ProjectMemberRole.member, ProjectMemberRole.guest, True),
            (ProjectMemberRole.member, ProjectMemberRole.member, True),
            (ProjectMemberRole.member, ProjectMemberRole.admin, False),
            (ProjectMemberRole.admin, ProjectMemberRole.guest, True),
            (ProjectMemberRole.admin, ProjectMemberRole.member, True),
            (ProjectMemberRole.admin, ProjectMemberRole.admin, True),
        ],
    )
    async def test_role_floor(
        self,
        member_role: ProjectMemberRole,
        minimum: ProjectMemberRole,
        should_pass: bool,
    ) -> None:
        # Pin: admin > member > guest, monotonic.  Drift in ordering
        # would let guests destroy resources or block admins from
        # legitimate operations.
        principal = _user_principal()
        project = _project()

        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=member_role)
            )
        )

        if should_pass:
            await access.require_role(session, principal, project, minimum=minimum)
        else:
            with pytest.raises(NotPermitted):
                await access.require_role(session, principal, project, minimum=minimum)
