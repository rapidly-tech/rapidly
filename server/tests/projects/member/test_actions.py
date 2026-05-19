"""Tests for ``rapidly.projects.member.actions``.

Invariants pinned:

- ``create`` requires the ``admin`` project role.
- ``create`` rejects users who aren't members of the project's workspace.
- ``create`` enforces ``(project_id, user_id)`` uniqueness.
- ``update`` and ``delete`` require the ``admin`` project role.
- Demoting or removing the only remaining admin is blocked.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import BadRequest, NotPermitted, ResourceAlreadyExists
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectMember, ProjectMemberRole, User
from rapidly.projects.member import actions as member_actions
from rapidly.projects.member.types import ProjectMemberCreate, ProjectMemberUpdate


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _member(role: ProjectMemberRole = ProjectMemberRole.member) -> ProjectMember:
    return ProjectMember(
        id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
        role=role,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_role_gate_admin_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.member.actions._ensure_admin", _ensure)

        with pytest.raises(NotPermitted):
            await member_actions.create(
                session,
                principal,
                ProjectMemberCreate(project_id=uuid4(), user_id=uuid4()),
            )

    async def test_rejects_user_not_in_workspace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=None))
        )

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=uuid4(), workspace_id=uuid4())

        monkeypatch.setattr("rapidly.projects.member.actions._ensure_admin", _ensure)

        with pytest.raises(BadRequest):
            await member_actions.create(
                session,
                principal,
                ProjectMemberCreate(project_id=uuid4(), user_id=uuid4()),
            )

    async def test_duplicate_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=(uuid4(),)))
        )

        project = MagicMock(id=uuid4(), workspace_id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr("rapidly.projects.member.actions._ensure_admin", _ensure)

        repo = MagicMock()
        repo.get_by_project_and_user = AsyncMock(return_value=_member())

        with patch(
            "rapidly.projects.member.actions.ProjectMemberRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await member_actions.create(
                    session,
                    principal,
                    ProjectMemberCreate(project_id=project.id, user_id=uuid4()),
                )


@pytest.mark.asyncio
class TestUpdateDelete:
    async def test_update_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()
        member = _member()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.member.actions._ensure_admin", _ensure)

        with pytest.raises(NotPermitted):
            await member_actions.update(
                session,
                principal,
                member,
                ProjectMemberUpdate(role=ProjectMemberRole.admin),
            )

    async def test_delete_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()
        member = _member()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.member.actions._ensure_admin", _ensure)

        with pytest.raises(NotPermitted):
            await member_actions.delete(session, principal, member)

    async def test_cannot_demote_last_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        member = _member(role=ProjectMemberRole.admin)
        session = MagicMock()
        # No other admins remain in the project.
        session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=None))
        )

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=member.project_id)

        monkeypatch.setattr("rapidly.projects.member.actions._ensure_admin", _ensure)

        with pytest.raises(BadRequest):
            await member_actions.update(
                session,
                principal,
                member,
                ProjectMemberUpdate(role=ProjectMemberRole.member),
            )

    async def test_cannot_delete_last_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        member = _member(role=ProjectMemberRole.admin)
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=None))
        )

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=member.project_id)

        monkeypatch.setattr("rapidly.projects.member.actions._ensure_admin", _ensure)

        with pytest.raises(BadRequest):
            await member_actions.delete(session, principal, member)
