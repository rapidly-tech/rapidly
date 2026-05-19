"""Tests for ``rapidly.projects.subscriber.actions``.

Invariants pinned:

- ``subscribe`` requires the work item to be readable.
- ``subscribe`` rejects duplicate subscriptions for the same (user, work item).
- ``unsubscribe`` is self-only: a user cannot unsubscribe someone else even
  if they can read the subscription row.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import ResourceAlreadyExists, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, WorkItemSubscriber
from rapidly.projects.subscriber import actions as sub_actions


def _principal(uid: Any = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uid or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _subscription(user_id: Any, work_item_id: Any) -> WorkItemSubscriber:
    return WorkItemSubscriber(id=uuid4(), work_item_id=work_item_id, user_id=user_id)


@pytest.mark.asyncio
class TestSubscribe:
    async def test_unreadable_work_item_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _unreadable(*_a: Any, **_k: Any) -> Any:
            raise ResourceNotFound()

        monkeypatch.setattr(
            "rapidly.projects.subscriber.actions._readable_work_item", _unreadable
        )

        with pytest.raises(ResourceNotFound):
            await sub_actions.subscribe(MagicMock(), principal, work_item_id=uuid4())

    async def test_duplicate_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        wi_id = uuid4()
        wi = MagicMock(id=wi_id, project_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        monkeypatch.setattr(
            "rapidly.projects.subscriber.actions._readable_work_item", _readable
        )

        repo = MagicMock()
        repo.get_for_user_and_work_item = AsyncMock(
            return_value=_subscription(principal.subject.id, wi_id)
        )

        with patch(
            "rapidly.projects.subscriber.actions.WorkItemSubscriberRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await sub_actions.subscribe(MagicMock(), principal, work_item_id=wi_id)

    async def test_creates_with_calling_user(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``user_id`` must come from the auth subject, not from any request."""
        principal = _principal()
        wi_id = uuid4()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wi_id, project_id=uuid4())

        monkeypatch.setattr(
            "rapidly.projects.subscriber.actions._readable_work_item", _readable
        )

        repo = MagicMock()
        repo.get_for_user_and_work_item = AsyncMock(return_value=None)

        created: list[Any] = []

        async def _create(obj: Any, flush: bool = False) -> Any:
            created.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.projects.subscriber.actions.WorkItemSubscriberRepository.from_session",
            return_value=repo,
        ):
            await sub_actions.subscribe(MagicMock(), principal, work_item_id=wi_id)

        assert created[0].user_id == principal.subject.id
        assert created[0].work_item_id == wi_id


@pytest.mark.asyncio
class TestUnsubscribe:
    async def test_self_can_unsubscribe(self) -> None:
        principal = _principal()
        sub = _subscription(principal.subject.id, uuid4())

        repo = MagicMock()
        repo.soft_delete = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.subscriber.actions.WorkItemSubscriberRepository.from_session",
            return_value=repo,
        ):
            await sub_actions.unsubscribe(MagicMock(), principal, sub)

        assert repo.soft_delete.await_count == 1

    async def test_cannot_unsubscribe_someone_else(self) -> None:
        """Pin: a user can't silently mute a teammate's notifications."""
        principal = _principal()
        sub = _subscription(uuid4(), uuid4())  # different user

        repo = MagicMock()
        repo.soft_delete = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.subscriber.actions.WorkItemSubscriberRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceNotFound):
                await sub_actions.unsubscribe(MagicMock(), principal, sub)

        repo.soft_delete.assert_not_called()
