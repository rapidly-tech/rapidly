"""Tests for ``rapidly.projects.estimate.actions``.

Estimates are admin-only — they shape every work-item's velocity
calculation, so guests/members must not be able to change the scale
under the team.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.errors import NotPermitted, ResourceAlreadyExists
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    EstimateType,
    ProjectEstimate,
    ProjectMemberRole,
    User,
)
from rapidly.projects.estimate import actions as estimate_actions
from rapidly.projects.estimate.types import (
    ProjectEstimateCreate,
    ProjectEstimatePointCreate,
    ProjectEstimateUpdate,
)


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _estimate(project_id: UUID | None = None) -> ProjectEstimate:
    return ProjectEstimate(
        id=uuid4(),
        project_id=project_id or uuid4(),
        name="Fibonacci",
        type=EstimateType.points,
        is_active=False,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_create_requires_admin(self) -> None:
        # Pin: estimates shape every work item — admin-only.
        principal = _user_principal()
        session = MagicMock()

        project = MagicMock(id=uuid4())
        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=project)
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        with (
            patch(
                "rapidly.projects.estimate.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.estimate.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await estimate_actions.create(
                    session,
                    principal,
                    ProjectEstimateCreate(project_id=uuid4(), name="Fib"),
                )
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.admin

    async def test_duplicate_name_rejected_after_admin_check(self) -> None:
        principal = _user_principal()
        session = MagicMock()

        project = MagicMock(id=uuid4())
        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=project)
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        repo = MagicMock()
        repo.get_by_name = AsyncMock(return_value=_estimate())

        with (
            patch(
                "rapidly.projects.estimate.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.estimate.actions.ProjectEstimateRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.projects.estimate.actions.require_role",
                new_callable=AsyncMock,
            ),
        ):
            with pytest.raises(ResourceAlreadyExists):
                await estimate_actions.create(
                    session,
                    principal,
                    ProjectEstimateCreate(project_id=uuid4(), name="Fib"),
                )


@pytest.mark.asyncio
class TestUpdate:
    async def test_update_requires_admin(self) -> None:
        principal = _user_principal()
        estimate = _estimate()
        session = MagicMock()

        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=MagicMock())
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        with (
            patch(
                "rapidly.projects.estimate.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.estimate.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await estimate_actions.update(
                    session, principal, estimate, ProjectEstimateUpdate(name="x")
                )
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.admin


@pytest.mark.asyncio
class TestCreatePoint:
    async def test_create_point_requires_admin(self) -> None:
        # Pin: adding a point to an existing scale changes velocity
        # math for every work item — admin-only.
        principal = _user_principal()
        session = MagicMock()
        estimate = _estimate()

        # ``get`` is patched to short-circuit the estimate lookup.
        async def _fake_get(*_a: Any, **_k: Any) -> ProjectEstimate:
            return estimate

        project_repo = MagicMock()
        project_repo.get_one_or_none = AsyncMock(return_value=MagicMock())
        project_repo.get_readable_statement = MagicMock(return_value=MagicMock())
        project_repo.model = MagicMock()

        with (
            patch(
                "rapidly.projects.estimate.actions.get",
                side_effect=_fake_get,
            ),
            patch(
                "rapidly.projects.estimate.actions.ProjectRepository.from_session",
                return_value=project_repo,
            ),
            patch(
                "rapidly.projects.estimate.actions.require_role",
                side_effect=NotPermitted(),
            ) as gate,
        ):
            with pytest.raises(NotPermitted):
                await estimate_actions.create_point(
                    session,
                    principal,
                    ProjectEstimatePointCreate(
                        estimate_id=estimate.id, key=1, value="1"
                    ),
                )
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.admin
