"""Tests for ``rapidly.agents.workflow.actions``."""

from __future__ import annotations

from datetime import UTC
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
                is_archived=None,
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

    async def test_has_version_true_adds_where(self) -> None:
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
                has_version=True,
                pagination=PaginationParams(page=1, limit=10),
            )

        # has_version=True adds one .where for the IS NOT NULL
        # predicate.
        assert statement.where.call_count == 1

    async def test_has_version_false_adds_where(self) -> None:
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
                has_version=False,
                pagination=PaginationParams(page=1, limit=10),
            )

        # has_version=False adds one .where for the IS NULL
        # predicate. The two branches are exclusive — exactly
        # one of the two should fire, not both.
        assert statement.where.call_count == 1

    async def test_has_version_none_is_noop(self) -> None:
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
                has_version=None,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 0

    async def test_workspace_id_adds_where(self) -> None:
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
                workspace_id=uuid4(),
                pagination=PaginationParams(page=1, limit=10),
            )

        # workspace_id alone → +1 .where. The readable-statement
        # already filters to readable workspaces; this narrows to
        # one of them.
        assert statement.where.call_count == 1

    async def test_workspace_id_combines_with_name_and_has_version(self) -> None:
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
                workspace_id=uuid4(),
                name="rfi",
                has_version=True,
                pagination=PaginationParams(page=1, limit=10),
            )

        # workspace_id + name + has_version → +3 .where (additive).
        # Confirms the new predicate doesn't short-circuit the
        # existing ones.
        assert statement.where.call_count == 3


@pytest.mark.asyncio
class TestArchive:
    async def test_active_workflow_gets_archived_stamp(self) -> None:
        principal = _principal()
        workflow = Workflow(
            id=uuid4(), workspace_id=uuid4(), name="x", archived_at=None
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=workflow)

        with patch(
            "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
            return_value=repo,
        ):
            await actions.archive(MagicMock(), principal, workflow)

        repo.update.assert_awaited_once()
        _, kwargs = repo.update.call_args
        assert "archived_at" in kwargs["update_dict"]
        assert kwargs["update_dict"]["archived_at"] is not None
        assert kwargs.get("flush") is True

    async def test_already_archived_workflow_is_noop(self) -> None:
        # Idempotent — re-archiving must not bump the timestamp.
        # We assert by checking repo.update is never called.
        from datetime import datetime

        principal = _principal()
        existing = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
        workflow = Workflow(
            id=uuid4(), workspace_id=uuid4(), name="x", archived_at=existing
        )

        repo = MagicMock()
        repo.update = AsyncMock()

        with patch(
            "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
            return_value=repo,
        ):
            result = await actions.archive(MagicMock(), principal, workflow)

        repo.update.assert_not_awaited()
        assert result.archived_at == existing


@pytest.mark.asyncio
class TestUnarchive:
    async def test_archived_workflow_clears_stamp(self) -> None:
        from datetime import datetime

        principal = _principal()
        workflow = Workflow(
            id=uuid4(),
            workspace_id=uuid4(),
            name="x",
            archived_at=datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC),
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=workflow)

        with patch(
            "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
            return_value=repo,
        ):
            await actions.unarchive(MagicMock(), principal, workflow)

        repo.update.assert_awaited_once()
        _, kwargs = repo.update.call_args
        assert kwargs["update_dict"] == {"archived_at": None}

    async def test_already_active_workflow_is_noop(self) -> None:
        principal = _principal()
        workflow = Workflow(
            id=uuid4(), workspace_id=uuid4(), name="x", archived_at=None
        )

        repo = MagicMock()
        repo.update = AsyncMock()

        with patch(
            "rapidly.agents.workflow.actions.WorkflowRepository.from_session",
            return_value=repo,
        ):
            await actions.unarchive(MagicMock(), principal, workflow)

        repo.update.assert_not_awaited()


@pytest.mark.asyncio
class TestListArchivedFilter:
    """``is_archived`` is tri-state at the action layer: True (archived
    only) / False (active only) / None (both, the default). The route
    layer hard-codes False as the user-facing default so the chamber's
    list endpoint hides archived rows by default."""

    async def test_explicit_false_filters_to_active_only(self) -> None:
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
                is_archived=False,
                pagination=PaginationParams(page=1, limit=10),
            )

        # is_archived=False → +1 .where for ``archived_at IS NULL``.
        assert statement.where.call_count == 1

    async def test_explicit_true_filters_to_archived_only(self) -> None:
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
                is_archived=True,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 1

    async def test_none_disables_filter_entirely(self) -> None:
        # ``None`` (passed explicitly) means "both archived and
        # active" — neither IS NULL nor IS NOT NULL predicate fires.
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
                is_archived=None,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 0
