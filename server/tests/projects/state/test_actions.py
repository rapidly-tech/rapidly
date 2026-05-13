"""Tests for ``rapidly.projects.state.actions``.

Key invariants:
- ``create`` rejects unknown project (404), then requires member role,
  then enforces ``(project_id, name)`` uniqueness.
- ``update`` and ``delete`` go through ``_ensure_member`` so the role
  gate applies even when callers already have the loaded row.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.errors import NotPermitted, ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectMemberRole, ProjectState, StateGroup, User
from rapidly.projects.state import actions as state_actions
from rapidly.projects.state.types import ProjectStateCreate, ProjectStateUpdate


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _state(project_id: UUID | None = None) -> ProjectState:
    return ProjectState(
        id=uuid4(),
        project_id=project_id or uuid4(),
        name="Todo",
        color="#6b7280",
        group=StateGroup.unstarted,
        sequence=1000.0,
        is_default=False,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_unknown_project_404(self) -> None:
        principal = _user_principal()
        session = MagicMock()

        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=None)
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        with patch(
            "rapidly.projects.state.actions.ProjectRepository.from_session",
            return_value=project_repo,
        ):
            with pytest.raises(ResourceNotFound):
                await state_actions.create(
                    session,
                    principal,
                    ProjectStateCreate(
                        project_id=uuid4(),
                        name="Todo",
                        group=StateGroup.unstarted,
                    ),
                )

    async def test_role_gate_invoked_before_name_check(self) -> None:
        # Pin: role check runs BEFORE name lookup so a non-member
        # cannot probe state names by getting a 409 vs no-error.
        principal = _user_principal()
        session = MagicMock()

        project = MagicMock(id=uuid4())
        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=project)
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        repo = MagicMock()
        repo.get_by_name = AsyncMock()  # should not be reached

        with (
            patch(
                "rapidly.projects.state.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.state.actions.ProjectStateRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.state.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await state_actions.create(
                    session,
                    principal,
                    ProjectStateCreate(
                        project_id=uuid4(),
                        name="Todo",
                        group=StateGroup.unstarted,
                    ),
                )
            gate.assert_awaited_once()
            repo.get_by_name.assert_not_called()

    async def test_duplicate_name_rejected(self) -> None:
        principal = _user_principal()
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        project = MagicMock(id=uuid4())
        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=project)
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        repo = MagicMock()
        repo.get_by_name = AsyncMock(return_value=_state())

        with (
            patch(
                "rapidly.projects.state.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.state.actions.ProjectStateRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.state.actions.require_role",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(ResourceAlreadyExists):
                await state_actions.create(
                    session,
                    principal,
                    ProjectStateCreate(
                        project_id=uuid4(),
                        name="Todo",
                        group=StateGroup.unstarted,
                    ),
                )


@pytest.mark.asyncio
class TestRoleGateOnMutations:
    async def test_update_runs_member_gate(self) -> None:
        principal = _user_principal()
        state = _state()
        session = MagicMock()

        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=MagicMock())
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        with (
            patch(
                "rapidly.projects.state.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.state.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await state_actions.update(
                    session, principal, state, ProjectStateUpdate(name="Doing")
                )
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.member

    async def test_delete_runs_member_gate(self) -> None:
        principal = _user_principal()
        state = _state()
        session = MagicMock()

        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=MagicMock())
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        with (
            patch(
                "rapidly.projects.state.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.state.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await state_actions.delete(session, principal, state)
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.member
