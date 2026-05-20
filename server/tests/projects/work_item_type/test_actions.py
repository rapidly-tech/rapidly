"""Tests for ``rapidly.projects.work_item_type.actions``.

Invariants pinned:

- ``create``/``update``/``delete`` require the ``admin`` project role.
- ``create`` rejects duplicate names within the same project.
- ``update`` rejects a rename that collides with another type's name.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import NotPermitted, ResourceAlreadyExists
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, WorkItemType
from rapidly.projects.work_item_type import actions as type_actions
from rapidly.projects.work_item_type.types import (
    WorkItemTypeCreate,
    WorkItemTypeUpdate,
)


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _type(name: str = "Bug") -> WorkItemType:
    return WorkItemType(
        id=uuid4(),
        project_id=uuid4(),
        name=name,
        logo_props={},
        is_epic=False,
        is_default=False,
        is_active=True,
        sort_order=65535.0,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_admin_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()

        async def _no_admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.work_item_type.actions._ensure_admin", _no_admin
        )

        with pytest.raises(NotPermitted):
            await type_actions.create(
                MagicMock(),
                principal,
                WorkItemTypeCreate(project_id=uuid4(), name="Bug"),
            )

    async def test_duplicate_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()
        project = MagicMock(id=uuid4())

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr(
            "rapidly.projects.work_item_type.actions._ensure_admin", _admin
        )

        repo = MagicMock()
        repo.get_by_project_and_name = AsyncMock(return_value=_type("Bug"))

        with patch(
            "rapidly.projects.work_item_type.actions.WorkItemTypeRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await type_actions.create(
                    MagicMock(),
                    principal,
                    WorkItemTypeCreate(project_id=project.id, name="Bug"),
                )


@pytest.mark.asyncio
class TestUpdateDelete:
    async def test_update_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()
        wit = _type()

        async def _no_admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.work_item_type.actions._ensure_admin", _no_admin
        )

        with pytest.raises(NotPermitted):
            await type_actions.update(
                MagicMock(), principal, wit, WorkItemTypeUpdate(name="Renamed")
            )

    async def test_delete_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()
        wit = _type()

        async def _no_admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.work_item_type.actions._ensure_admin", _no_admin
        )

        with pytest.raises(NotPermitted):
            await type_actions.delete(MagicMock(), principal, wit)

    async def test_rename_to_existing_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If another type already owns the target name, reject the rename."""
        principal = _user_principal()
        wit = _type("Bug")

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wit.project_id)

        monkeypatch.setattr(
            "rapidly.projects.work_item_type.actions._ensure_admin", _admin
        )

        repo = MagicMock()
        repo.get_by_project_and_name = AsyncMock(return_value=_type("Task"))

        with patch(
            "rapidly.projects.work_item_type.actions.WorkItemTypeRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await type_actions.update(
                    MagicMock(), principal, wit, WorkItemTypeUpdate(name="Task")
                )
