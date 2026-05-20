"""Tests for ``rapidly.projects.vote.actions``.

Invariants pinned:

- ``cast`` rejects votes on work items the caller can't read.
- ``cast`` is an upsert: same-value cast is a no-op, different-value
  cast updates rather than inserts.
- ``retract`` is self-only — non-owner gets 404 (no oracle).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, WorkItemVote
from rapidly.projects.vote import actions as vote_actions
from rapidly.projects.vote.types import WorkItemVoteCast


def _principal(uid: Any = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uid or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _vote(user_id: Any, work_item_id: Any, value: int = 1) -> WorkItemVote:
    return WorkItemVote(
        id=uuid4(),
        work_item_id=work_item_id,
        user_id=user_id,
        vote=value,
    )


@pytest.mark.asyncio
class TestCast:
    async def test_unreadable_work_item_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _unreadable(*_a: Any, **_k: Any) -> Any:
            raise ResourceNotFound()

        monkeypatch.setattr(
            "rapidly.projects.vote.actions._readable_work_item", _unreadable
        )

        with pytest.raises(ResourceNotFound):
            await vote_actions.cast(
                MagicMock(),
                principal,
                WorkItemVoteCast(work_item_id=uuid4(), vote=1),
            )

    async def test_same_value_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        existing = _vote(principal.subject.id, uuid4(), value=1)

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=existing.work_item_id)

        monkeypatch.setattr(
            "rapidly.projects.vote.actions._readable_work_item", _readable
        )

        repo = MagicMock()
        repo.get_for_work_item_and_user = AsyncMock(return_value=existing)
        repo.update = AsyncMock(return_value=existing)
        repo.create = AsyncMock(return_value=existing)

        with patch(
            "rapidly.projects.vote.actions.WorkItemVoteRepository.from_session",
            return_value=repo,
        ):
            result = await vote_actions.cast(
                MagicMock(),
                principal,
                WorkItemVoteCast(work_item_id=existing.work_item_id, vote=1),
            )

        assert result is existing
        repo.update.assert_not_called()
        repo.create.assert_not_called()

    async def test_flip_updates_existing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        existing = _vote(principal.subject.id, uuid4(), value=1)

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=existing.work_item_id)

        monkeypatch.setattr(
            "rapidly.projects.vote.actions._readable_work_item", _readable
        )

        repo = MagicMock()
        repo.get_for_work_item_and_user = AsyncMock(return_value=existing)
        repo.update = AsyncMock(return_value=existing)

        with patch(
            "rapidly.projects.vote.actions.WorkItemVoteRepository.from_session",
            return_value=repo,
        ):
            await vote_actions.cast(
                MagicMock(),
                principal,
                WorkItemVoteCast(work_item_id=existing.work_item_id, vote=-1),
            )

        assert repo.update.await_count == 1
        _, kwargs = repo.update.call_args
        assert kwargs["update_dict"] == {"vote": -1}


@pytest.mark.asyncio
class TestRetract:
    async def test_self_can_retract(self) -> None:
        principal = _principal()
        vote = _vote(principal.subject.id, uuid4())

        repo = MagicMock()
        repo.soft_delete = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.vote.actions.WorkItemVoteRepository.from_session",
            return_value=repo,
        ):
            await vote_actions.retract(MagicMock(), principal, vote)

        assert repo.soft_delete.await_count == 1

    async def test_cannot_retract_someone_elses(self) -> None:
        principal = _principal()
        # Vote belongs to a different user.
        vote = _vote(uuid4(), uuid4())

        repo = MagicMock()
        repo.soft_delete = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.vote.actions.WorkItemVoteRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceNotFound):
                await vote_actions.retract(MagicMock(), principal, vote)

        repo.soft_delete.assert_not_called()
