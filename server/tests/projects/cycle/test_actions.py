"""Tests for ``rapidly.projects.cycle.actions``.

Invariants pinned:

- ``create`` requires ``member`` role on the parent project.
- ``create`` rejects ``end_date < start_date`` (also enforced on update).
- ``create`` enforces ``(project_id, name)`` uniqueness.
- ``archive`` and ``delete`` require ``admin`` role — a member can run
  the sprint, only an admin can erase it from the board.
- ``add_work_items`` rejects work items from a different project.
- ``add_work_items`` resurrects a soft-deleted membership instead of
  inserting a duplicate row.
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
    ProjectCycle,
    ProjectCycleWorkItem,
    ProjectMemberRole,
    User,
)
from rapidly.projects.cycle import actions as cycle_actions
from rapidly.projects.cycle.types import ProjectCycleCreate, ProjectCycleUpdate


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _cycle(project_id: UUID | None = None) -> ProjectCycle:
    return ProjectCycle(
        id=uuid4(),
        project_id=project_id or uuid4(),
        name="Sprint 1",
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

        monkeypatch.setattr("rapidly.projects.cycle.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await cycle_actions.create(
                session,
                principal,
                ProjectCycleCreate(project_id=uuid4(), name="Sprint 1"),
            )

    async def test_end_before_start_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=uuid4())

        monkeypatch.setattr("rapidly.projects.cycle.actions._ensure_member", _ensure)

        start = datetime(2026, 5, 1, tzinfo=UTC)
        end = start - timedelta(days=1)
        with pytest.raises(BadRequest):
            await cycle_actions.create(
                session,
                principal,
                ProjectCycleCreate(
                    project_id=uuid4(),
                    name="Sprint 1",
                    start_date=start,
                    end_date=end,
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

        monkeypatch.setattr("rapidly.projects.cycle.actions._ensure_member", _ensure)

        repo = MagicMock()
        repo.get_by_name = AsyncMock(return_value=_cycle(project_id=project.id))

        with patch(
            "rapidly.projects.cycle.actions.ProjectCycleRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await cycle_actions.create(
                    session,
                    principal,
                    ProjectCycleCreate(project_id=project.id, name="Sprint 1"),
                )


@pytest.mark.asyncio
class TestUpdate:
    async def test_end_before_start_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        cycle = _cycle()
        session = MagicMock()

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=cycle.project_id)

        monkeypatch.setattr("rapidly.projects.cycle.actions._ensure_member", _ensure)

        start = datetime(2026, 5, 1, tzinfo=UTC)
        end = start - timedelta(days=2)

        with pytest.raises(BadRequest):
            await cycle_actions.update(
                session,
                principal,
                cycle,
                ProjectCycleUpdate(start_date=start, end_date=end),
            )


@pytest.mark.asyncio
class TestArchiveDelete:
    async def test_archive_requires_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        cycle = _cycle()
        session = MagicMock()

        observed: dict[str, Any] = {}

        async def _ensure(*_a: Any, **kwargs: Any) -> Any:
            observed["minimum"] = kwargs.get("minimum")
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.cycle.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await cycle_actions.archive(session, principal, cycle)
        assert observed["minimum"] == ProjectMemberRole.admin

    async def test_delete_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _user_principal()
        cycle = _cycle()
        session = MagicMock()

        observed: dict[str, Any] = {}

        async def _ensure(*_a: Any, **kwargs: Any) -> Any:
            observed["minimum"] = kwargs.get("minimum")
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.cycle.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await cycle_actions.delete(session, principal, cycle)
        assert observed["minimum"] == ProjectMemberRole.admin

    async def test_unarchive_requires_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        cycle = _cycle()
        session = MagicMock()

        observed: dict[str, Any] = {}

        async def _ensure(*_a: Any, **kwargs: Any) -> Any:
            observed["minimum"] = kwargs.get("minimum")
            raise NotPermitted()

        monkeypatch.setattr("rapidly.projects.cycle.actions._ensure_member", _ensure)

        with pytest.raises(NotPermitted):
            await cycle_actions.unarchive(session, principal, cycle)
        assert observed["minimum"] == ProjectMemberRole.admin


@pytest.mark.asyncio
class TestAddWorkItems:
    async def test_rejects_work_items_from_other_project(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: cycle membership is scoped to a single project.  Allowing
        # cross-project members would let a workspace member silently
        # add another team's items to a cycle they read.
        principal = _user_principal()
        cycle = _cycle()
        session = MagicMock()
        # No matches → `_verify_work_items_in_project` raises.
        session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=cycle.project_id)

        monkeypatch.setattr("rapidly.projects.cycle.actions._ensure_member", _ensure)

        with pytest.raises(BadRequest):
            await cycle_actions.add_work_items(
                session, principal, cycle, [uuid4(), uuid4()]
            )

    async def test_resurrects_soft_deleted_link(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a previously-removed work item re-added to a cycle must
        # reuse the existing row (clear ``deleted_at``) — inserting a
        # second row would collide with the unique constraint.
        principal = _user_principal()
        cycle = _cycle()
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        work_item_id = uuid4()
        # Verify pass-through.
        session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[(work_item_id,)]))
        )

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=cycle.project_id)

        monkeypatch.setattr("rapidly.projects.cycle.actions._ensure_member", _ensure)

        previously_deleted = ProjectCycleWorkItem(
            id=uuid4(),
            cycle_id=cycle.id,
            work_item_id=work_item_id,
        )
        previously_deleted.deleted_at = datetime(2026, 1, 1, tzinfo=UTC)

        repo = MagicMock()
        repo.existing_for_cycle = AsyncMock(
            return_value={work_item_id: previously_deleted}
        )
        repo.update = AsyncMock()

        with patch(
            "rapidly.projects.cycle.actions.ProjectCycleWorkItemRepository.from_session",
            return_value=repo,
        ):
            await cycle_actions.add_work_items(
                session, principal, cycle, [work_item_id]
            )

        repo.update.assert_awaited_once()
        assert repo.update.await_args is not None
        kwargs = repo.update.await_args.kwargs
        assert kwargs["update_dict"] == {"deleted_at": None}
        session.add.assert_not_called()
