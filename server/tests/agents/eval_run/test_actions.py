"""Tests for ``rapidly.agents.eval_run.actions`` — list filters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.agents.eval_run import actions
from rapidly.core.pagination import PaginationParams
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User
from rapidly.models.eval_run import EvalRunStatus


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
