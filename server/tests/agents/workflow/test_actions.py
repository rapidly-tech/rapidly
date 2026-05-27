"""Tests for ``rapidly.agents.workflow.actions``."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.agents.workflow import actions
from rapidly.agents.workflow.types import WorkflowCreate, WorkflowUpdate
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, Workflow


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_persists_with_no_current_version(self) -> None:
        principal = _principal()
        workspace_id = uuid4()

        captured: list[Any] = []
        repo = MagicMock()

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
            return_value=repo,
        ):
            await actions.create(
                MagicMock(),
                principal,
                WorkflowCreate(workspace_id=workspace_id, name="rfi-triage"),
            )

        assert captured[0].workspace_id == workspace_id
        assert captured[0].name == "rfi-triage"
        # ``current_version_id`` only gets set when the versioning
        # submodule's "publish" call lands. Bare-create starts null.
        assert captured[0].current_version_id is None

    async def test_passes_through_project_id(self) -> None:
        principal = _principal()
        workspace_id = uuid4()
        project_id = uuid4()

        captured: list[Any] = []
        repo = MagicMock()

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
            return_value=repo,
        ):
            await actions.create(
                MagicMock(),
                principal,
                WorkflowCreate(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    name="rfi-triage",
                ),
            )

        assert captured[0].project_id == project_id


@pytest.mark.asyncio
class TestUpdate:
    async def test_empty_payload_noop(self) -> None:
        principal = _principal()
        workflow = Workflow(
            id=uuid4(), workspace_id=uuid4(), name="x", description=None
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=workflow)

        with patch(
            "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
            return_value=repo,
        ):
            result = await actions.update(
                MagicMock(), principal, workflow, WorkflowUpdate()
            )

        assert result is workflow
        repo.update.assert_not_called()

    async def test_partial_update_applies_only_set_fields(self) -> None:
        principal = _principal()
        workflow = Workflow(
            id=uuid4(), workspace_id=uuid4(), name="old-name", description=None
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=workflow)

        with patch(
            "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
            return_value=repo,
        ):
            await actions.update(
                MagicMock(),
                principal,
                workflow,
                WorkflowUpdate(name="new-name"),
            )

        repo.update.assert_awaited_once()
        _, kwargs = repo.update.call_args
        assert kwargs["update_dict"] == {"name": "new-name"}


@pytest.mark.asyncio
class TestDelete:
    async def test_soft_deletes(self) -> None:
        principal = _principal()
        workflow = Workflow(id=uuid4(), workspace_id=uuid4(), name="x")

        repo = MagicMock()
        repo.soft_delete = AsyncMock()

        with patch(
            "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
            return_value=repo,
        ):
            await actions.delete(MagicMock(), principal, workflow)

        repo.soft_delete.assert_awaited_once_with(workflow)


@pytest.mark.asyncio
class TestListWorkflows:
    """``name`` filter — substring match through the standard escape
    pattern. We can't assert SQL text through a MagicMock chain (per
    the project's documented test pattern) so we count ``.where``
    calls and inspect the escape side-effect indirectly."""

    async def test_no_name_no_extra_where(self) -> None:
        principal = _principal()
        statement = MagicMock()
        statement.where.return_value = statement

        repo = MagicMock()
        repo.get_readable_statement.return_value = statement

        with (
            patch(
                "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.workflow.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_workflows(
                MagicMock(),
                principal,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 0

    async def test_name_filter_adds_where(self) -> None:
        principal = _principal()
        statement = MagicMock()
        statement.where.return_value = statement

        repo = MagicMock()
        repo.get_readable_statement.return_value = statement

        with (
            patch(
                "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.workflow.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_workflows(
                MagicMock(),
                principal,
                name="triage",
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 1

    async def test_empty_name_is_noop(self) -> None:
        principal = _principal()
        statement = MagicMock()
        statement.where.return_value = statement

        repo = MagicMock()
        repo.get_readable_statement.return_value = statement

        with (
            patch(
                "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.workflow.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            from rapidly.core.pagination import PaginationParams

            await actions.list_workflows(
                MagicMock(),
                principal,
                name="   ",
                pagination=PaginationParams(page=1, limit=10),
            )

        # Whitespace-only name is ignored — same contract as the
        # projects/labels list filter.
        assert statement.where.call_count == 0
