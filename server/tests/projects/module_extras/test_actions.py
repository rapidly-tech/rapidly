"""Tests for ``rapidly.projects.module_extras.actions``.

Invariants pinned for members:
- ``add_member`` requires the ``member`` project role.
- ``add_member`` rejects users not in the project's workspace.
- ``add_member`` rejects duplicate (module, user) pairs.

Invariants pinned for links:
- ``create_link`` requires the ``member`` project role.
- ``update_link`` allows clearing the title back to NULL without clearing the URL.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import BadRequest, NotPermitted, ResourceAlreadyExists
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectModuleLink, ProjectModuleMember, User
from rapidly.projects.module_extras import actions as me_actions
from rapidly.projects.module_extras.types import (
    ProjectModuleLinkUpdate,
    ProjectModuleMemberCreate,
)


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _module() -> Any:
    return MagicMock(id=uuid4(), project_id=uuid4())


def _link(title: str | None = "Spec") -> ProjectModuleLink:
    return ProjectModuleLink(
        id=uuid4(),
        module_id=uuid4(),
        url="https://figma.com/x",
        title=title,
    )


def _member() -> ProjectModuleMember:
    return ProjectModuleMember(id=uuid4(), module_id=uuid4(), user_id=uuid4())


@pytest.mark.asyncio
class TestAddMember:
    async def test_role_gate_member_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        module = _module()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return module

        async def _no_role(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._readable_module", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._ensure_member", _no_role
        )

        with pytest.raises(NotPermitted):
            await me_actions.add_member(
                MagicMock(),
                principal,
                ProjectModuleMemberCreate(module_id=module.id, user_id=uuid4()),
            )

    async def test_cross_workspace_user_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        module = _module()
        project = MagicMock(id=module.project_id, workspace_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return module

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        async def _bad_workspace(*_a: Any, **_k: Any) -> None:
            raise BadRequest("User is not a member of this module's workspace.")

        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._readable_module", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._ensure_member", _ensure
        )
        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._ensure_user_in_workspace",
            _bad_workspace,
        )

        with pytest.raises(BadRequest):
            await me_actions.add_member(
                MagicMock(),
                principal,
                ProjectModuleMemberCreate(module_id=module.id, user_id=uuid4()),
            )

    async def test_duplicate_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        module = _module()
        project = MagicMock(id=module.project_id, workspace_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return module

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._readable_module", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._ensure_member", _ensure
        )
        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._ensure_user_in_workspace",
            _ok,
        )

        repo = MagicMock()
        repo.get_for_module_and_user = AsyncMock(return_value=_member())

        with patch(
            "rapidly.projects.module_extras.actions.ProjectModuleMemberRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await me_actions.add_member(
                    MagicMock(),
                    principal,
                    ProjectModuleMemberCreate(module_id=module.id, user_id=uuid4()),
                )


@pytest.mark.asyncio
class TestLinks:
    async def test_create_requires_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        module = _module()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return module

        async def _no_role(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._readable_module", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._ensure_member", _no_role
        )

        from rapidly.projects.module_extras.types import ProjectModuleLinkCreate

        with pytest.raises(NotPermitted):
            await me_actions.create_link(
                MagicMock(),
                principal,
                ProjectModuleLinkCreate(
                    module_id=module.id,
                    url="https://figma.com/x",  # type: ignore[arg-type]
                ),
            )

    async def test_update_can_clear_title_to_null(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        link = _link(title="Old")
        module = _module()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return module

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._readable_module", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.module_extras.actions._ensure_member", _ok
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=link)

        with patch(
            "rapidly.projects.module_extras.actions.ProjectModuleLinkRepository.from_session",
            return_value=repo,
        ):
            await me_actions.update_link(
                MagicMock(),
                principal,
                link,
                ProjectModuleLinkUpdate(title=None),
            )

        assert repo.update.await_count == 1
        _, kwargs = repo.update.call_args
        assert kwargs["update_dict"] == {"title": None}
