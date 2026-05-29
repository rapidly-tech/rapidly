"""Tests for ``rapidly.agents.eval_run.actions`` — list filters + cancel."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.agents.eval_run import actions
from rapidly.core.pagination import PaginationParams
from rapidly.errors import NotPermitted
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import EvalRun, User
from rapidly.models.eval_run import AssertionStrategy, EvalRunStatus


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _mock_repo() -> tuple[MagicMock, MagicMock]:
    statement = MagicMock()
    statement.order_by.return_value = statement
    statement.where.return_value = statement
    repo = MagicMock()
    repo.get_readable_statement.return_value = statement
    return repo, statement


@pytest.mark.asyncio
class TestListEvalRuns:
    """``status`` filter — added in M5.26 for parity with the
    runs list endpoint. Test pattern matches workflow:
    count ``.where`` calls rather than asserting SQL text."""

    async def test_no_filters_no_extra_where(self) -> None:
        principal = _principal()
        repo, statement = _mock_repo()

        with (
            patch(
                "rapidly.agents.eval_run.actions.EvalRunRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.eval_run.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await actions.list_eval_runs(
                MagicMock(),
                principal,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 0

    async def test_status_filter_adds_where(self) -> None:
        principal = _principal()
        repo, statement = _mock_repo()

        with (
            patch(
                "rapidly.agents.eval_run.actions.EvalRunRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.eval_run.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await actions.list_eval_runs(
                MagicMock(),
                principal,
                status=EvalRunStatus.failed,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 1

    async def test_status_combines_with_other_filters(self) -> None:
        # Each filter adds one .where; all three together adds
        # three. Confirms the new filter doesn't accidentally
        # short-circuit the existing dataset_id / workflow_version_id
        # predicates.
        principal = _principal()
        repo, statement = _mock_repo()

        with (
            patch(
                "rapidly.agents.eval_run.actions.EvalRunRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.eval_run.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await actions.list_eval_runs(
                MagicMock(),
                principal,
                dataset_id=uuid4(),
                workflow_version_id=uuid4(),
                status=EvalRunStatus.succeeded,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 3

    async def test_assertion_strategy_filter_adds_where(self) -> None:
        principal = _principal()
        repo, statement = _mock_repo()

        with (
            patch(
                "rapidly.agents.eval_run.actions.EvalRunRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.eval_run.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await actions.list_eval_runs(
                MagicMock(),
                principal,
                assertion_strategy=AssertionStrategy.llm_judge,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 1

    async def test_all_four_filters_combine_additively(self) -> None:
        # All four filters together must add four independent
        # .where predicates — confirms no short-circuit between
        # assertion_strategy and the three earlier ones.
        principal = _principal()
        repo, statement = _mock_repo()

        with (
            patch(
                "rapidly.agents.eval_run.actions.EvalRunRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.eval_run.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await actions.list_eval_runs(
                MagicMock(),
                principal,
                dataset_id=uuid4(),
                workflow_version_id=uuid4(),
                status=EvalRunStatus.failed,
                assertion_strategy=AssertionStrategy.exact_match,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 4

    async def test_workspace_id_adds_where(self) -> None:
        principal = _principal()
        repo, statement = _mock_repo()

        with (
            patch(
                "rapidly.agents.eval_run.actions.EvalRunRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.eval_run.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await actions.list_eval_runs(
                MagicMock(),
                principal,
                workspace_id=uuid4(),
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 1

    async def test_all_five_filters_combine_additively(self) -> None:
        # All five filters → +5 .where. Confirms the new
        # workspace_id predicate doesn't short-circuit any of the
        # four earlier ones.
        principal = _principal()
        repo, statement = _mock_repo()

        with (
            patch(
                "rapidly.agents.eval_run.actions.EvalRunRepository.from_session",
                return_value=repo,
            ),
            patch(
                "rapidly.agents.eval_run.actions.paginate",
                new=AsyncMock(return_value=([], 0)),
            ),
        ):
            await actions.list_eval_runs(
                MagicMock(),
                principal,
                workspace_id=uuid4(),
                dataset_id=uuid4(),
                workflow_version_id=uuid4(),
                status=EvalRunStatus.failed,
                assertion_strategy=AssertionStrategy.llm_judge,
                pagination=PaginationParams(page=1, limit=10),
            )

        assert statement.where.call_count == 5


@pytest.mark.asyncio
class TestCancel:
    async def test_pending_flips_to_cancelled(self) -> None:
        principal = _principal()
        eval_run = EvalRun(
            id=uuid4(),
            workspace_id=uuid4(),
            dataset_id=uuid4(),
            workflow_version_id=uuid4(),
            status=EvalRunStatus.pending,
        )
        session = MagicMock()
        session.flush = AsyncMock()

        result = await actions.cancel(session, principal, eval_run)

        assert result.status == EvalRunStatus.cancelled
        assert result.completed_at is not None
        session.flush.assert_awaited_once()

    async def test_running_flips_to_cancelled(self) -> None:
        principal = _principal()
        eval_run = EvalRun(
            id=uuid4(),
            workspace_id=uuid4(),
            dataset_id=uuid4(),
            workflow_version_id=uuid4(),
            status=EvalRunStatus.running,
        )
        session = MagicMock()
        session.flush = AsyncMock()

        result = await actions.cancel(session, principal, eval_run)

        assert result.status == EvalRunStatus.cancelled

    @pytest.mark.parametrize(
        "terminal",
        [EvalRunStatus.succeeded, EvalRunStatus.failed, EvalRunStatus.cancelled],
    )
    async def test_terminal_status_refuses(self, terminal: EvalRunStatus) -> None:
        # Cancelling an already-terminal run must raise NotPermitted so
        # the caller sees a clear 403, not a silent no-op.
        principal = _principal()
        eval_run = EvalRun(
            id=uuid4(),
            workspace_id=uuid4(),
            dataset_id=uuid4(),
            workflow_version_id=uuid4(),
            status=terminal,
        )
        session = MagicMock()
        session.flush = AsyncMock()

        with pytest.raises(NotPermitted):
            await actions.cancel(session, principal, eval_run)

        # No flush should have happened — the refusal is before any
        # state mutation.
        session.flush.assert_not_awaited()
