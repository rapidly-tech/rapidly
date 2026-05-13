"""Tests for ``rapidly.projects.module.actions``.

Invariants pinned (mirror of the cycle suite, with module-specific
guards):

- ``create`` requires ``member`` role on the parent project.
- ``create`` rejects ``target_date < start_date``.
- ``create`` enforces ``(project_id, name)`` uniqueness.
- ``archive`` and ``delete`` require ``admin`` role.
- ``add_work_items`` rejects items from a different project.
- ``add_work_items`` resurrects a soft-deleted membership.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.errors import (
    BadRequest,
    NotPermitted,
    ResourceAlreadyExists,
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    ModuleStatus,
    ProjectMemberRole,
    ProjectModule,
    ProjectModuleWorkItem,
    User,
)
from rapidly.projects.module import actions as module_actions
from rapidly.projects.module.types import (
    ProjectModuleCreate,
    ProjectModuleUpdate,
)


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _module(project_id: UUID | None = None) -> ProjectModule:
    return ProjectModule(
        id=uuid4(),
        project_id=project_id or uuid4(),
        name="Billing v2",
        status=ModuleStatus.planned,
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

        monkeypatch.setattr("rapidly.projects.module.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await module_actions.create(
                session,
                principal,
                ProjectModuleCreate(project_id=uuid4(), name="Billing v2"),
            )

    async def test_target_before_start_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=uuid4())

        monkeypatch.setattr("rapidly.projects.module.actions._ensure_member", _ensure)

        start = datetime(2026, 5, 1, tzinfo=UTC)
        target = start - timedelta(days=1)
        with pytest.raises(BadRequest):
            await module_actions.create(
                session,
                principal,
                ProjectModuleCreate(
                    project_id=uuid4(),
                    name="Billing v2",
                    start_date=start,
                    target_date=target,
                ),
            )

    async def test_duplicate_name_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()
        project = MagicMock(id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr("rapidly.projects.module.actions._ensure_member", _ensure)

        repo = MagicMock()
        repo.get_by_name = AsyncMock(return_value=_module(project_id=project.id))

        with patch(
            "rapidly.projects.module.actions.ProjectModuleRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await module_actions.create(
                    session,
                    principal,
                    ProjectModuleCreate(project_id=project.id, name="Billing v2"),
                )


@pytest.mark.asyncio
class TestUpdate:
    async def test_target_before_start_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        module = _module()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=module.project_id)

        monkeypatch.setattr("rapidly.projects.module.actions._ensure_member", _ensure)

        start = datetime(2026, 5, 1, tzinfo=UTC)
        target = start - timedelta(days=2)

        with pytest.raises(BadRequest):
            await module_actions.update(
                session,
                principal,
                module,
                ProjectModuleUpdate(start_date=start, target_date=target),
            )


@pytest.mark.asyncio
class TestArchiveDelete:
    async def test_archive_requires_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        module = _module()
        session = MagicMock()

        observed: dict[str, Any] = {}

        async def _ensure(*_a: Any, **kwargs: Any) -> Any:
            observed["minimum"] = kwargs.get("minimum")
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.module.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await module_actions.archive(session, principal, module)
        assert observed["minimum"] == ProjectMemberRole.admin

    async def test_unarchive_requires_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: unarchive is symmetric to archive — same admin floor.
        principal = _user_principal()
        module = _module()
        session = MagicMock()

        observed: dict[str, Any] = {}

        async def _ensure(*_a: Any, **kwargs: Any) -> Any:
            observed["minimum"] = kwargs.get("minimum")
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.module.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await module_actions.unarchive(session, principal, module)
        assert observed["minimum"] == ProjectMemberRole.admin

    async def test_delete_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()
        module = _module()
        session = MagicMock()

        observed: dict[str, Any] = {}

        async def _ensure(*_a: Any, **kwargs: Any) -> Any:
            observed["minimum"] = kwargs.get("minimum")
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.module.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await module_actions.delete(session, principal, module)
        assert observed["minimum"] == ProjectMemberRole.admin


@pytest.mark.asyncio
class TestAddWorkItems:
    async def test_rejects_work_items_from_other_project(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        module = _module()
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=module.project_id)

        monkeypatch.setattr("rapidly.projects.module.actions._ensure_member", _ensure)

        with pytest.raises(BadRequest):
            await module_actions.add_work_items(session, principal, module, [uuid4()])

    async def test_resurrects_soft_deleted_link(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        module = _module()
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        work_item_id = uuid4()
        session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[(work_item_id,)]))
        )

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=module.project_id)

        monkeypatch.setattr("rapidly.projects.module.actions._ensure_member", _ensure)

        previously_deleted = ProjectModuleWorkItem(
            id=uuid4(), module_id=module.id, work_item_id=work_item_id
        )
        previously_deleted.deleted_at = datetime(2026, 1, 1, tzinfo=UTC)

        repo = MagicMock()
        repo.existing_for_module = AsyncMock(
            return_value={work_item_id: previously_deleted}
        )
        repo.update = AsyncMock()

        with patch(
            "rapidly.projects.module.actions.ProjectModuleWorkItemRepository.from_session",
            return_value=repo,
        ):
            await module_actions.add_work_items(
                session, principal, module, [work_item_id]
            )

        repo.update.assert_awaited_once()
        assert repo.update.await_args is not None
        kwargs = repo.update.await_args.kwargs
        assert kwargs["update_dict"] == {"deleted_at": None}
        session.add.assert_not_called()
