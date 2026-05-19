"""Tests for ``rapidly.projects.view.actions``.

Pins:
- ``create`` requires ``member`` role on the parent project.
- ``create`` enforces ``(project_id, name)`` uniqueness.
- ``archive`` / ``unarchive`` require ``member``.
- ``delete`` requires ``admin``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.errors import NotPermitted, ResourceAlreadyExists
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectMemberRole, ProjectView, User
from rapidly.projects.view import actions as view_actions
from rapidly.projects.view.types import ProjectViewCreate


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _view(project_id: UUID | None = None) -> ProjectView:
    return ProjectView(
        id=uuid4(),
        project_id=project_id or uuid4(),
        name="My View",
        filters={"priority": ["high"]},
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_role_gate_member_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await view_actions.create(
                session,
                principal,
                ProjectViewCreate(project_id=uuid4(), name="My View"),
            )

    async def test_duplicate_name_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()
        project = MagicMock(id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure)

        repo = MagicMock()
        repo.get_by_name = AsyncMock(return_value=_view(project_id=project.id))

        with patch(
            "rapidly.projects.view.actions.ProjectViewRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await view_actions.create(
                    session,
                    principal,
                    ProjectViewCreate(project_id=project.id, name="My View"),
                )


@pytest.mark.asyncio
class TestArchiveDelete:
    async def test_archive_requires_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Archive is reversible and per-row — same floor as update.
        principal = _user_principal()
        view = _view()
        session = MagicMock()

        observed: dict[str, Any] = {}

        async def _ensure(*_a: Any, **kwargs: Any) -> Any:
            observed["minimum"] = kwargs.get("minimum")
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await view_actions.archive(session, principal, view)
        assert observed["minimum"] == ProjectMemberRole.member

    async def test_unarchive_requires_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        view = _view()
        session = MagicMock()

        observed: dict[str, Any] = {}

        async def _ensure(*_a: Any, **kwargs: Any) -> Any:
            observed["minimum"] = kwargs.get("minimum")
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await view_actions.unarchive(session, principal, view)
        assert observed["minimum"] == ProjectMemberRole.member

    async def test_delete_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: delete is destructive even with soft-delete, so it gates
        # on admin to match the rest of the project-domain pattern.
        principal = _user_principal()
        view = _view()
        session = MagicMock()

        observed: dict[str, Any] = {}

        async def _ensure(*_a: Any, **kwargs: Any) -> Any:
            observed["minimum"] = kwargs.get("minimum")
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await view_actions.delete(session, principal, view)
        assert observed["minimum"] == ProjectMemberRole.admin
