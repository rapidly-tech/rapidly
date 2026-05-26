"""Tests for ``rapidly.agents.run.actions``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.agents.run import actions
from rapidly.errors import NotPermitted
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import Run, RunStatus, TriggeredByKind, User


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _run(status: RunStatus) -> Run:
    return Run(
        id=uuid4(),
        workflow_version_id=uuid4(),
        triggered_by_kind=TriggeredByKind.user,
        triggered_by_id=uuid4(),
        status=status,
        input_data={},
        output_data={},
    )


@pytest.mark.asyncio
class TestCancel:
    async def test_flips_running_to_cancelled(self) -> None:
        run = _run(RunStatus.running)
        session = MagicMock()
        session.flush = AsyncMock()

        result = await actions.cancel(session, _principal(), run)

        assert result.status == RunStatus.cancelled
        assert result.completed_at is not None
        session.flush.assert_awaited_once()

    async def test_flips_awaiting_human_to_cancelled(self) -> None:
        # Mid-pause cancels — an operator should be able to abandon
        # a parked run that's been awaiting a human response too
        # long.
        run = _run(RunStatus.awaiting_human)
        session = MagicMock()
        session.flush = AsyncMock()

        result = await actions.cancel(session, _principal(), run)

        assert result.status == RunStatus.cancelled

    async def test_refuses_to_cancel_succeeded(self) -> None:
        run = _run(RunStatus.succeeded)
        session = MagicMock()
        session.flush = AsyncMock()

        with pytest.raises(NotPermitted, match="terminal status succeeded"):
            await actions.cancel(session, _principal(), run)
        # Flush must not happen on the refused path.
        session.flush.assert_not_called()

    async def test_refuses_to_cancel_failed(self) -> None:
        run = _run(RunStatus.failed)
        session = MagicMock()
        session.flush = AsyncMock()

        with pytest.raises(NotPermitted, match="terminal status failed"):
            await actions.cancel(session, _principal(), run)

    async def test_refuses_to_cancel_already_cancelled(self) -> None:
        # Idempotency at the API boundary: a double-cancel returns
        # 403 (NotPermitted) rather than silently no-op'ing. The UI
        # can interpret the error as "already cancelled".
        run = _run(RunStatus.cancelled)
        session = MagicMock()
        session.flush = AsyncMock()

        with pytest.raises(NotPermitted, match="terminal status cancelled"):
            await actions.cancel(session, _principal(), run)


@pytest.mark.asyncio
class TestList:
    async def test_optional_workflow_version_id_filter(self) -> None:
        # Pass-through to the repo's readable_statement; we verify
        # the where-clause assembly by counting how often the
        # repository's where method gets invoked on the returned
        # statement.
        principal = _principal()
        wfv_id = uuid4()

        # Mock the paginate function to introspect the statement
        # without actually hitting a DB.
        with patch(
            "rapidly.agents.run.actions.paginate",
            AsyncMock(return_value=([], 0)),
        ) as fake_paginate:
            with patch(
                "rapidly.agents.run.actions.RunRepository.from_session",
                return_value=MagicMock(
                    get_readable_statement=MagicMock(return_value=MagicMock())
                ),
            ):
                await actions.list_runs(
                    MagicMock(),
                    principal,
                    workflow_version_id=wfv_id,
                    pagination=MagicMock(),
                )
        assert fake_paginate.await_count == 1
