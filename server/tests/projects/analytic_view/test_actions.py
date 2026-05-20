"""Tests for ``rapidly.projects.analytic_view.actions``.

Invariants pinned:

- ``create`` rejects a workspace the caller can't access.
- ``create`` rejects a project from a different workspace than the view.
- ``update`` is a no-op when the payload has no fields set.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import BadRequest, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import AnalyticView, User
from rapidly.projects.analytic_view import actions as av_actions
from rapidly.projects.analytic_view.types import (
    AnalyticViewCreate,
    AnalyticViewUpdate,
)


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _view(workspace_id: Any = None) -> AnalyticView:
    return AnalyticView(
        id=uuid4(),
        workspace_id=workspace_id or uuid4(),
        name="Sprint burnup",
        query={"chart": "burnup"},
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_unreadable_workspace_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _no_access(*_a: Any, **_k: Any) -> None:
            raise ResourceNotFound("Workspace not found.")

        monkeypatch.setattr(
            "rapidly.projects.analytic_view.actions._ensure_workspace_access",
            _no_access,
        )

        with pytest.raises(ResourceNotFound):
            await av_actions.create(
                MagicMock(),
                principal,
                AnalyticViewCreate(workspace_id=uuid4(), name="x"),
            )

    async def test_cross_workspace_project_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Project must belong to the same workspace as the view."""
        principal = _principal()
        workspace_id = uuid4()
        project = MagicMock(id=uuid4(), workspace_id=uuid4())  # different workspace

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        async def _member(*_a: Any, **_k: Any) -> Any:
            return project

        monkeypatch.setattr(
            "rapidly.projects.analytic_view.actions._ensure_workspace_access", _ok
        )
        monkeypatch.setattr(
            "rapidly.projects.analytic_view.actions._ensure_member", _member
        )

        with pytest.raises(BadRequest):
            await av_actions.create(
                MagicMock(),
                principal,
                AnalyticViewCreate(
                    workspace_id=workspace_id,
                    project_id=project.id,
                    name="Bug burndown",
                ),
            )


@pytest.mark.asyncio
class TestUpdate:
    async def test_empty_payload_is_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        view = _view()

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.analytic_view.actions._ensure_workspace_access", _ok
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=view)

        with patch(
            "rapidly.projects.analytic_view.actions.AnalyticViewRepository.from_session",
            return_value=repo,
        ):
            result = await av_actions.update(
                MagicMock(), principal, view, AnalyticViewUpdate()
            )

        assert result is view
        repo.update.assert_not_called()
