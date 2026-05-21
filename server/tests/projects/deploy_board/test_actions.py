"""Tests for ``rapidly.projects.deploy_board.actions``.

Invariants pinned:

- ``create`` requires admin (not just member).
- ``create`` rejects a duplicate board on the same project.
- ``create`` always generates a fresh server-side token.
- ``rotate_token`` issues a new token, replacing the old one.
- ``update`` is a no-op when the payload has no set fields.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import NotPermitted, ResourceAlreadyExists
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectDeployBoard, User
from rapidly.projects.deploy_board import actions as board_actions
from rapidly.projects.deploy_board.types import (
    ProjectDeployBoardCreate,
    ProjectDeployBoardUpdate,
)


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _board(project_id: Any = None, token: str = "t-old") -> ProjectDeployBoard:
    return ProjectDeployBoard(
        id=uuid4(),
        project_id=project_id or uuid4(),
        token=token,
        is_public=False,
        show_comments=False,
        show_reactions=False,
        show_votes=False,
        show_intake_form=False,
        view_props={},
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_admin_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()

        async def _no_admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.deploy_board.actions._ensure_admin", _no_admin
        )

        with pytest.raises(NotPermitted):
            await board_actions.create(
                MagicMock(),
                principal,
                ProjectDeployBoardCreate(project_id=uuid4()),
            )

    async def test_rejects_duplicate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        project_id = uuid4()

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=project_id)

        monkeypatch.setattr(
            "rapidly.projects.deploy_board.actions._ensure_admin", _admin
        )

        repo = MagicMock()
        repo.get_by_project = AsyncMock(return_value=_board(project_id=project_id))

        with patch(
            "rapidly.projects.deploy_board.actions.ProjectDeployBoardRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await board_actions.create(
                    MagicMock(),
                    principal,
                    ProjectDeployBoardCreate(project_id=project_id),
                )

    async def test_generates_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Token must come from the server, not the request body."""
        principal = _principal()
        project_id = uuid4()

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=project_id)

        monkeypatch.setattr(
            "rapidly.projects.deploy_board.actions._ensure_admin", _admin
        )

        captured: list[Any] = []
        repo = MagicMock()
        repo.get_by_project = AsyncMock(return_value=None)

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.projects.deploy_board.actions.ProjectDeployBoardRepository.from_session",
            return_value=repo,
        ):
            await board_actions.create(
                MagicMock(),
                principal,
                ProjectDeployBoardCreate(project_id=project_id),
            )

        assert captured[0].token
        assert len(captured[0].token) >= 32


@pytest.mark.asyncio
class TestRotateToken:
    async def test_issues_new_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        board = _board(token="t-old")

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=board.project_id)

        monkeypatch.setattr(
            "rapidly.projects.deploy_board.actions._ensure_admin", _admin
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=board)

        with patch(
            "rapidly.projects.deploy_board.actions.ProjectDeployBoardRepository.from_session",
            return_value=repo,
        ):
            await board_actions.rotate_token(MagicMock(), principal, board)

        assert repo.update.await_count == 1
        _, kwargs = repo.update.call_args
        new_token = kwargs["update_dict"]["token"]
        assert new_token and new_token != "t-old"


@pytest.mark.asyncio
class TestUpdate:
    async def test_empty_payload_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        board = _board()

        async def _admin(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=board.project_id)

        monkeypatch.setattr(
            "rapidly.projects.deploy_board.actions._ensure_admin", _admin
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=board)

        with patch(
            "rapidly.projects.deploy_board.actions.ProjectDeployBoardRepository.from_session",
            return_value=repo,
        ):
            result = await board_actions.update(
                MagicMock(), principal, board, ProjectDeployBoardUpdate()
            )

        assert result is board
        repo.update.assert_not_called()
