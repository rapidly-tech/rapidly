"""Tests for ``rapidly.projects.label.actions`` — focus on the role
gate and the parent-label cross-project guard."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.errors import BadRequest, NotPermitted, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectLabel, ProjectMemberRole, User
from rapidly.projects.label import actions as label_actions
from rapidly.projects.label.types import ProjectLabelCreate, ProjectLabelUpdate


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _label(
    project_id: UUID | None = None, parent_id: UUID | None = None
) -> ProjectLabel:
    return ProjectLabel(
        id=uuid4(),
        project_id=project_id or uuid4(),
        parent_id=parent_id,
        name="bug",
        color="#ef4444",
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_parent_in_other_project_rejected(self) -> None:
        # Pin: parent label MUST belong to the same project as the
        # child.  Drift would let users build cross-project hier-
        # archies and leak labels across projects.
        principal = _user_principal()
        session = MagicMock()
        target_project_id = uuid4()
        other_project_id = uuid4()
        parent_id = uuid4()

        project = MagicMock(id=target_project_id)
        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=project)
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=MagicMock())
        repo.get_one_or_none = AsyncMock(
            return_value=_label(project_id=other_project_id)
        )

        with (
            patch(
                "rapidly.projects.label.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.label.actions.ProjectLabelRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.label.actions.require_role",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(BadRequest):
                await label_actions.create(
                    session,
                    principal,
                    ProjectLabelCreate(
                        project_id=target_project_id,
                        parent_id=parent_id,
                        name="critical",
                    ),
                )

    async def test_missing_parent_404(self) -> None:
        principal = _user_principal()
        session = MagicMock()
        project_id = uuid4()

        project = MagicMock(id=project_id)
        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=project)
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=None)

        with (
            patch(
                "rapidly.projects.label.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.label.actions.ProjectLabelRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.label.actions.require_role",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(ResourceNotFound):
                await label_actions.create(
                    session,
                    principal,
                    ProjectLabelCreate(
                        project_id=project_id,
                        parent_id=uuid4(),
                        name="critical",
                    ),
                )


@pytest.mark.asyncio
class TestRoleGate:
    async def test_update_blocked_for_non_member(self) -> None:
        principal = _user_principal()
        label = _label()
        session = MagicMock()

        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=MagicMock())
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        with (
            patch(
                "rapidly.projects.label.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.label.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await label_actions.update(
                    session, principal, label, ProjectLabelUpdate(name="x")
                )
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.member
