"""Tests for ``rapidly.projects.reaction.actions``.

Invariants pinned:

- ``react_to_*`` requires the parent (work item / comment) to be readable.
- ``react_to_*`` rejects a duplicate triplet (parent, user, emoji).
- ``unreact_*`` is self-only — a user cannot remove someone else's reaction.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    User,
    WorkItemCommentReaction,
    WorkItemReaction,
)
from rapidly.projects.reaction import actions as r_actions
from rapidly.projects.reaction.types import (
    WorkItemCommentReactionCreate,
    WorkItemReactionCreate,
)


def _principal(uid: Any = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uid or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _wi_reaction(user_id: Any, work_item_id: Any) -> WorkItemReaction:
    return WorkItemReaction(
        id=uuid4(),
        work_item_id=work_item_id,
        user_id=user_id,
        reaction="👍",
    )


def _comment_reaction(user_id: Any, comment_id: Any) -> WorkItemCommentReaction:
    return WorkItemCommentReaction(
        id=uuid4(),
        comment_id=comment_id,
        user_id=user_id,
        reaction="🎉",
    )


@pytest.mark.asyncio
class TestWorkItemReact:
    async def test_unreadable_work_item_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _unreadable(*_a: Any, **_k: Any) -> Any:
            raise ResourceNotFound()

        monkeypatch.setattr(
            "rapidly.projects.reaction.actions._readable_work_item", _unreadable
        )

        with pytest.raises(ResourceNotFound):
            await r_actions.react_to_work_item(
                MagicMock(),
                principal,
                WorkItemReactionCreate(work_item_id=uuid4(), reaction="👍"),
            )

    async def test_duplicate_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        wi_id = uuid4()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wi_id)

        monkeypatch.setattr(
            "rapidly.projects.reaction.actions._readable_work_item", _readable
        )

        repo = MagicMock()
        repo.get_for_triplet = AsyncMock(
            return_value=_wi_reaction(principal.subject.id, wi_id)
        )

        with patch(
            "rapidly.projects.reaction.actions.WorkItemReactionRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await r_actions.react_to_work_item(
                    MagicMock(),
                    principal,
                    WorkItemReactionCreate(work_item_id=wi_id, reaction="👍"),
                )

    async def test_uses_caller_user_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``user_id`` must come from the auth subject, not from any body field."""
        principal = _principal()
        wi_id = uuid4()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wi_id)

        monkeypatch.setattr(
            "rapidly.projects.reaction.actions._readable_work_item", _readable
        )

        captured: list[Any] = []
        repo = MagicMock()
        repo.get_for_triplet = AsyncMock(return_value=None)

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.projects.reaction.actions.WorkItemReactionRepository.from_session",
            return_value=repo,
        ):
            await r_actions.react_to_work_item(
                MagicMock(),
                principal,
                WorkItemReactionCreate(work_item_id=wi_id, reaction="🚀"),
            )

        assert captured[0].user_id == principal.subject.id
        assert captured[0].work_item_id == wi_id
        assert captured[0].reaction == "🚀"


@pytest.mark.asyncio
class TestWorkItemUnreact:
    async def test_self_can_remove(self) -> None:
        principal = _principal()
        reaction = _wi_reaction(principal.subject.id, uuid4())

        repo = MagicMock()
        repo.soft_delete = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.reaction.actions.WorkItemReactionRepository.from_session",
            return_value=repo,
        ):
            await r_actions.unreact_work_item(MagicMock(), principal, reaction)

        assert repo.soft_delete.await_count == 1

    async def test_cannot_remove_someone_elses(self) -> None:
        """Pin: a user cannot remove another user's reaction."""
        principal = _principal()
        reaction = _wi_reaction(uuid4(), uuid4())  # different user

        repo = MagicMock()
        repo.soft_delete = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.reaction.actions.WorkItemReactionRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceNotFound):
                await r_actions.unreact_work_item(MagicMock(), principal, reaction)

        repo.soft_delete.assert_not_called()


@pytest.mark.asyncio
class TestCommentReact:
    async def test_unreadable_comment_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _unreadable(*_a: Any, **_k: Any) -> Any:
            raise ResourceNotFound()

        monkeypatch.setattr(
            "rapidly.projects.reaction.actions._readable_comment", _unreadable
        )

        with pytest.raises(ResourceNotFound):
            await r_actions.react_to_comment(
                MagicMock(),
                principal,
                WorkItemCommentReactionCreate(comment_id=uuid4(), reaction="🎉"),
            )

    async def test_cannot_remove_someone_elses(self) -> None:
        principal = _principal()
        reaction = _comment_reaction(uuid4(), uuid4())  # different user

        repo = MagicMock()
        repo.soft_delete = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.reaction.actions.WorkItemCommentReactionRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceNotFound):
                await r_actions.unreact_comment(MagicMock(), principal, reaction)

        repo.soft_delete.assert_not_called()
