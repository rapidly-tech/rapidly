"""Tests for ``rapidly.projects.view.actions``.

Invariants pinned:

- ``create`` requires the caller to be a project member.
- Owners can update their own non-locked views.
- Non-owner members cannot mutate someone else's view (admin required).
- ``is_locked`` blocks even the owner from updating until an admin unlocks.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import NotPermitted, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectView, ProjectViewAccess, User
from rapidly.projects.view import actions as view_actions
from rapidly.projects.view.types import ProjectViewCreate, ProjectViewUpdate


def _principal(uid: Any = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uid or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _view(owner_id: Any = None, is_locked: bool = False) -> ProjectView:
    return ProjectView(
        id=uuid4(),
        project_id=uuid4(),
        owner_id=owner_id,
        name="My view",
        filters={},
        display_filters={},
        display_properties={},
        access=ProjectViewAccess.public,
        is_locked=is_locked,
        sort_order=65535.0,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_member_can_create(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        session = MagicMock()
        project = MagicMock(id=uuid4(), workspace_id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure)

        repo = MagicMock()
        created = _view(owner_id=principal.subject.id)
        repo.create = AsyncMock(return_value=created)

        with patch(
            "rapidly.projects.view.actions.ProjectViewRepository.from_session",
            return_value=repo,
        ):
            result = await view_actions.create(
                session,
                principal,
                ProjectViewCreate(project_id=project.id, name="My view"),
            )

        assert result is created
        assert repo.create.await_count == 1

    async def test_non_member_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await view_actions.create(
                session,
                principal,
                ProjectViewCreate(project_id=uuid4(), name="My view"),
            )


@pytest.mark.asyncio
class TestUpdate:
    async def test_owner_can_update_unlocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner_id = uuid4()
        principal = _principal(uid=owner_id)
        view = _view(owner_id=owner_id)
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=view.project_id)

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure)

        repo = MagicMock()
        repo.update = AsyncMock(return_value=view)

        with patch(
            "rapidly.projects.view.actions.ProjectViewRepository.from_session",
            return_value=repo,
        ):
            await view_actions.update(
                session, principal, view, ProjectViewUpdate(name="renamed")
            )

        assert repo.update.await_count == 1

    async def test_non_owner_member_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-owner members must NOT be able to update someone else's view."""
        principal = _principal()  # different uid
        view = _view(owner_id=uuid4())  # owned by someone else
        session = MagicMock()

        async def _ensure_mem(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=view.project_id)

        async def _require_admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure_mem)
        monkeypatch.setattr(
            "rapidly.projects.view.actions.require_role", _require_admin
        )

        with pytest.raises(NotPermitted):
            await view_actions.update(
                session, principal, view, ProjectViewUpdate(name="hijack")
            )

    async def test_lock_blocks_owner(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Even the owner can't update a locked view without admin role."""
        owner_id = uuid4()
        principal = _principal(uid=owner_id)
        view = _view(owner_id=owner_id, is_locked=True)
        session = MagicMock()

        async def _ensure_mem(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=view.project_id)

        async def _require_admin(*_a: Any, **_k: Any) -> None:
            # The lock check calls require_role with admin; reject it.
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure_mem)
        monkeypatch.setattr(
            "rapidly.projects.view.actions.require_role", _require_admin
        )

        with pytest.raises(NotPermitted):
            await view_actions.update(
                session, principal, view, ProjectViewUpdate(name="renamed")
            )


@pytest.mark.asyncio
class TestDeleteArchive:
    async def test_owner_can_delete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        owner_id = uuid4()
        principal = _principal(uid=owner_id)
        view = _view(owner_id=owner_id)
        session = MagicMock()

        async def _ensure_mem(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=view.project_id)

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure_mem)

        repo = MagicMock()
        repo.soft_delete = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.view.actions.ProjectViewRepository.from_session",
            return_value=repo,
        ):
            await view_actions.delete(session, principal, view)

        assert repo.soft_delete.await_count == 1

    async def test_archive_sets_archived_at(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner_id = uuid4()
        principal = _principal(uid=owner_id)
        view = _view(owner_id=owner_id)
        session = MagicMock()

        async def _ensure_mem(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=view.project_id)

        monkeypatch.setattr("rapidly.projects.view.actions._ensure_member", _ensure_mem)

        repo = MagicMock()
        repo.update = AsyncMock(return_value=view)

        with patch(
            "rapidly.projects.view.actions.ProjectViewRepository.from_session",
            return_value=repo,
        ):
            await view_actions.archive(session, principal, view)

        assert repo.update.await_count == 1
        _, kwargs = repo.update.call_args
        assert "archived_at" in kwargs["update_dict"]
        assert kwargs["update_dict"]["archived_at"] is not None


@pytest.mark.asyncio
class TestProjectNotFound:
    async def test_ensure_member_raises_when_project_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        session = MagicMock()

        # Real ``_ensure_member`` raises ResourceNotFound when the project
        # repo returns None, regardless of role gate.  Patch the repo
        # directly so we exercise the helper's own logic.
        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=None)
        project_repo.get_readable_statement = MagicMock(
            return_value=MagicMock(where=MagicMock(return_value=MagicMock()))
        )
        project_repo.model = MagicMock(id=MagicMock())

        with patch(
            "rapidly.projects.view.actions.ProjectRepository.from_session",
            return_value=project_repo,
        ):
            with pytest.raises(ResourceNotFound):
                await view_actions._ensure_member(session, principal, uuid4())
