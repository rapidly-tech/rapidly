"""Tests for ``rapidly.projects.member_invite.actions``.

Invariants pinned:

- ``create`` requires the admin project role.
- ``create`` rejects an invitee who is not a workspace member.
- ``create`` rejects when the invitee is already a project member.
- ``create`` rejects duplicate *pending* invites.
- ``accept`` rejects a leaked token used by someone other than the invitee.
- ``decline`` is self-only.
- ``revoke`` requires admin role and only acts on pending invites.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import (
    BadRequest,
    NotPermitted,
    ResourceAlreadyExists,
    ResourceNotFound,
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    ProjectMemberInvite,
    ProjectMemberInviteStatus,
    ProjectMemberRole,
    User,
)
from rapidly.projects.member_invite import actions as inv_actions
from rapidly.projects.member_invite.types import ProjectMemberInviteCreate


def _principal(uid: Any = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uid or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _invite(
    invitee_id: Any,
    status: ProjectMemberInviteStatus = ProjectMemberInviteStatus.pending,
) -> ProjectMemberInvite:
    return ProjectMemberInvite(
        id=uuid4(),
        project_id=uuid4(),
        invitee_id=invitee_id,
        invited_by_id=None,
        role=ProjectMemberRole.member.value,
        token="t-" + uuid4().hex,
        status=status,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_admin_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()

        async def _no_admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._ensure_admin", _no_admin
        )

        with pytest.raises(NotPermitted):
            await inv_actions.create(
                MagicMock(),
                principal,
                ProjectMemberInviteCreate(project_id=uuid4(), invitee_id=uuid4()),
            )

    async def test_rejects_non_workspace_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        project = MagicMock(id=uuid4(), workspace_id=uuid4())

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return project

        async def _not_in_workspace(*_a: Any, **_k: Any) -> None:
            raise BadRequest("User is not a member of this project's workspace.")

        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._ensure_admin", _admin
        )
        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._ensure_user_in_workspace",
            _not_in_workspace,
        )

        with pytest.raises(BadRequest):
            await inv_actions.create(
                MagicMock(),
                principal,
                ProjectMemberInviteCreate(project_id=project.id, invitee_id=uuid4()),
            )

    async def test_rejects_existing_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        project = MagicMock(id=uuid4(), workspace_id=uuid4())

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return project

        async def _in_ws(*_a: Any, **_k: Any) -> None:
            return None

        async def _existing(*_a: Any, **_k: Any) -> Any:
            return MagicMock()  # truthy → user is already a member

        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._ensure_admin", _admin
        )
        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._ensure_user_in_workspace",
            _in_ws,
        )
        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._existing_membership",
            _existing,
        )

        with pytest.raises(ResourceAlreadyExists):
            await inv_actions.create(
                MagicMock(),
                principal,
                ProjectMemberInviteCreate(project_id=project.id, invitee_id=uuid4()),
            )

    async def test_rejects_duplicate_pending(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        invitee_id = uuid4()
        project = MagicMock(id=uuid4(), workspace_id=uuid4())

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return project

        async def _in_ws(*_a: Any, **_k: Any) -> None:
            return None

        async def _no_existing(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._ensure_admin", _admin
        )
        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._ensure_user_in_workspace",
            _in_ws,
        )
        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._existing_membership",
            _no_existing,
        )

        repo = MagicMock()
        repo.get_pending_for_user_and_project = AsyncMock(
            return_value=_invite(invitee_id)
        )

        with patch(
            "rapidly.projects.member_invite.actions.ProjectMemberInviteRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await inv_actions.create(
                    MagicMock(),
                    principal,
                    ProjectMemberInviteCreate(
                        project_id=project.id, invitee_id=invitee_id
                    ),
                )


@pytest.mark.asyncio
class TestAccept:
    async def test_leaked_token_rejected_for_other_user(self) -> None:
        """Possessing the token isn't enough — caller identity must match."""
        attacker = _principal()
        invitee_id = uuid4()
        invite = _invite(invitee_id)

        repo = MagicMock()
        repo.get_by_token = AsyncMock(return_value=invite)

        with patch(
            "rapidly.projects.member_invite.actions.ProjectMemberInviteRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(NotPermitted):
                await inv_actions.accept(MagicMock(), attacker, token=invite.token)

    async def test_unknown_token_404s(self) -> None:
        principal = _principal()
        repo = MagicMock()
        repo.get_by_token = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.member_invite.actions.ProjectMemberInviteRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceNotFound):
                await inv_actions.accept(MagicMock(), principal, token="nope")

    async def test_already_accepted_404s(self) -> None:
        principal = _principal()
        invite = _invite(
            principal.subject.id, status=ProjectMemberInviteStatus.accepted
        )

        repo = MagicMock()
        repo.get_by_token = AsyncMock(return_value=invite)

        with patch(
            "rapidly.projects.member_invite.actions.ProjectMemberInviteRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceNotFound):
                await inv_actions.accept(MagicMock(), principal, token=invite.token)


@pytest.mark.asyncio
class TestDecline:
    async def test_self_only(self) -> None:
        principal = _principal()
        # invite addressed to someone else
        invite = _invite(uuid4())

        with pytest.raises(NotPermitted):
            await inv_actions.decline(MagicMock(), principal, invite)

    async def test_only_pending_can_decline(self) -> None:
        principal = _principal()
        invite = _invite(
            principal.subject.id, status=ProjectMemberInviteStatus.accepted
        )

        with pytest.raises(BadRequest):
            await inv_actions.decline(MagicMock(), principal, invite)


@pytest.mark.asyncio
class TestRevoke:
    async def test_admin_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        invite = _invite(uuid4())

        async def _no_admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._ensure_admin", _no_admin
        )

        with pytest.raises(NotPermitted):
            await inv_actions.revoke(MagicMock(), principal, invite)

    async def test_only_pending_can_revoke(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        invite = _invite(uuid4(), status=ProjectMemberInviteStatus.declined)

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=invite.project_id)

        monkeypatch.setattr(
            "rapidly.projects.member_invite.actions._ensure_admin", _admin
        )

        with pytest.raises(BadRequest):
            await inv_actions.revoke(MagicMock(), principal, invite)
