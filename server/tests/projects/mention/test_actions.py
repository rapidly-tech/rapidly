"""Tests for ``rapidly.projects.mention.actions``.

Invariants pinned:

- ``create`` rejects mentions on comments the caller can't read.
- ``create`` rejects when caller is neither the comment author nor an admin.
- ``create`` rejects mentioning a user outside the workspace.
- ``create`` rejects duplicate (comment, mentioned_user) pairs.
- ``delete`` requires author-or-admin on the parent comment.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import (
    BadRequest,
    NotPermitted,
    ResourceAlreadyExists,
    ResourceNotFound,
)
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, WorkItemMention
from rapidly.projects.mention import actions as mention_actions
from rapidly.projects.mention.types import WorkItemMentionCreate


def _principal(uid: Any = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uid or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _comment(actor_id: Any) -> Any:
    return MagicMock(id=uuid4(), actor_id=actor_id, work_item_id=uuid4())


def _project() -> Any:
    return MagicMock(id=uuid4(), workspace_id=uuid4())


def _mention(comment_id: Any) -> WorkItemMention:
    return WorkItemMention(
        id=uuid4(),
        comment_id=comment_id,
        mentioned_user_id=uuid4(),
        mentioned_by_id=uuid4(),
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_unreadable_comment_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _unreadable(*_a: Any, **_k: Any) -> Any:
            raise ResourceNotFound()

        monkeypatch.setattr(
            "rapidly.projects.mention.actions._resolve_comment", _unreadable
        )

        with pytest.raises(ResourceNotFound):
            await mention_actions.create(
                MagicMock(),
                principal,
                WorkItemMentionCreate(comment_id=uuid4(), mentioned_user_id=uuid4()),
            )

    async def test_non_author_non_admin_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        comment = _comment(actor_id=uuid4())  # different author
        project = _project()

        async def _resolve(*_a: Any, **_k: Any) -> Any:
            return comment, MagicMock(), project

        async def _no_admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.mention.actions._resolve_comment", _resolve
        )
        monkeypatch.setattr(
            "rapidly.projects.mention.actions._ensure_author_or_admin", _no_admin
        )

        with pytest.raises(NotPermitted):
            await mention_actions.create(
                MagicMock(),
                principal,
                WorkItemMentionCreate(comment_id=comment.id, mentioned_user_id=uuid4()),
            )

    async def test_cross_workspace_target_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        comment = _comment(actor_id=principal.subject.id)
        project = _project()

        async def _resolve(*_a: Any, **_k: Any) -> Any:
            return comment, MagicMock(), project

        async def _ok_author(*_a: Any, **_k: Any) -> None:
            return None

        async def _cross_workspace(*_a: Any, **_k: Any) -> None:
            raise BadRequest("Mentioned user is not in this workspace.")

        monkeypatch.setattr(
            "rapidly.projects.mention.actions._resolve_comment", _resolve
        )
        monkeypatch.setattr(
            "rapidly.projects.mention.actions._ensure_author_or_admin", _ok_author
        )
        monkeypatch.setattr(
            "rapidly.projects.mention.actions._ensure_user_in_workspace",
            _cross_workspace,
        )

        with pytest.raises(BadRequest):
            await mention_actions.create(
                MagicMock(),
                principal,
                WorkItemMentionCreate(comment_id=comment.id, mentioned_user_id=uuid4()),
            )

    async def test_duplicate_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        comment = _comment(actor_id=principal.subject.id)
        project = _project()

        async def _resolve(*_a: Any, **_k: Any) -> Any:
            return comment, MagicMock(), project

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.mention.actions._resolve_comment", _resolve
        )
        monkeypatch.setattr(
            "rapidly.projects.mention.actions._ensure_author_or_admin", _ok
        )
        monkeypatch.setattr(
            "rapidly.projects.mention.actions._ensure_user_in_workspace", _ok
        )

        repo = MagicMock()
        repo.get_for_comment_and_user = AsyncMock(return_value=_mention(comment.id))

        with patch(
            "rapidly.projects.mention.actions.WorkItemMentionRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await mention_actions.create(
                    MagicMock(),
                    principal,
                    WorkItemMentionCreate(
                        comment_id=comment.id, mentioned_user_id=uuid4()
                    ),
                )


@pytest.mark.asyncio
class TestDelete:
    async def test_delete_requires_author_or_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        mention = _mention(uuid4())
        comment = _comment(actor_id=uuid4())  # different author
        project = _project()

        async def _resolve(*_a: Any, **_k: Any) -> Any:
            return comment, MagicMock(), project

        async def _no_admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.mention.actions._resolve_comment", _resolve
        )
        monkeypatch.setattr(
            "rapidly.projects.mention.actions._ensure_author_or_admin", _no_admin
        )

        with pytest.raises(NotPermitted):
            await mention_actions.delete(MagicMock(), principal, mention)
