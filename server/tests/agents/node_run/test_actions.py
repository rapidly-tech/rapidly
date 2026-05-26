"""Tests for ``rapidly.agents.node_run.actions``.

Read-only surface — the engine writes through the repo's inherited
create + update directly in M4.2. So the action-layer tests are
narrow: get / list / 404.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.agents.node_run import actions
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


@pytest.mark.asyncio
class TestGet:
    async def test_returns_node_run_when_present(self) -> None:
        node_run = MagicMock()
        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=node_run)

        with patch(
            "rapidly.agents.node_run.actions.NodeRunRepository.from_session",
            return_value=repo,
        ):
            result = await actions.get(MagicMock(), _principal(), uuid4())
        assert result is node_run

    async def test_returns_none_when_absent(self) -> None:
        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=None)

        with patch(
            "rapidly.agents.node_run.actions.NodeRunRepository.from_session",
            return_value=repo,
        ):
            result = await actions.get(MagicMock(), _principal(), uuid4())
        assert result is None


@pytest.mark.asyncio
class TestGetOrRaise:
    async def test_raises_on_missing(self) -> None:
        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=None)

        with patch(
            "rapidly.agents.node_run.actions.NodeRunRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceNotFound, match="Node run not found"):
                await actions.get_or_raise(MagicMock(), _principal(), uuid4())


@pytest.mark.asyncio
class TestListForRun:
    async def test_filters_by_run_id(self) -> None:
        principal = _principal()
        run_id = uuid4()

        with patch(
            "rapidly.agents.node_run.actions.paginate",
            AsyncMock(return_value=([], 0)),
        ) as fake_paginate:
            with patch(
                "rapidly.agents.node_run.actions.NodeRunRepository.from_session",
                return_value=MagicMock(
                    get_readable_statement=MagicMock(return_value=MagicMock())
                ),
            ):
                await actions.list_for_run(
                    MagicMock(),
                    principal,
                    run_id=run_id,
                    pagination=MagicMock(),
                )
        assert fake_paginate.await_count == 1
