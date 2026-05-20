"""Tests for ``rapidly.projects.intake.actions``.

Invariants pinned:

- ``create`` rejects duplicate (one intake row per work item).
- ``transition`` rejects illegal state-machine moves
  (e.g. accepted → snoozed).
- ``transition`` to snoozed requires a future ``snoozed_until``.
- ``transition`` to duplicate requires ``duplicate_to_id`` and
  rejects self-dup.
- ``transition`` to a same-status is a silent no-op.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import BadRequest, ResourceAlreadyExists
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    IntakeSource,
    IntakeStatus,
    IntakeWorkItem,
    User,
)
from rapidly.projects.intake import actions as intake_actions
from rapidly.projects.intake.types import (
    IntakeWorkItemCreate,
    IntakeWorkItemUpdate,
)


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _intake(
    status: IntakeStatus = IntakeStatus.pending,
    work_item_id: Any = None,
) -> IntakeWorkItem:
    return IntakeWorkItem(
        id=uuid4(),
        work_item_id=work_item_id or uuid4(),
        status=status,
        source=IntakeSource.api,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_duplicate_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        wi = MagicMock(id=uuid4(), project_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _member(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wi.project_id)

        monkeypatch.setattr(
            "rapidly.projects.intake.actions._readable_work_item", _readable
        )
        monkeypatch.setattr("rapidly.projects.intake.actions._ensure_member", _member)

        repo = MagicMock()
        repo.get_by_work_item = AsyncMock(return_value=_intake(work_item_id=wi.id))

        with patch(
            "rapidly.projects.intake.actions.IntakeWorkItemRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await intake_actions.create(
                    MagicMock(),
                    principal,
                    IntakeWorkItemCreate(work_item_id=wi.id),
                )


@pytest.mark.asyncio
class TestTransition:
    async def test_same_status_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        intake = _intake(status=IntakeStatus.pending)
        wi = MagicMock(id=intake.work_item_id, project_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _member(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wi.project_id)

        monkeypatch.setattr(
            "rapidly.projects.intake.actions._readable_work_item", _readable
        )
        monkeypatch.setattr("rapidly.projects.intake.actions._ensure_member", _member)

        result = await intake_actions.transition(
            MagicMock(),
            principal,
            intake,
            IntakeWorkItemUpdate(status=IntakeStatus.pending),
        )
        assert result is intake

    async def test_illegal_move_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """accepted → snoozed is not allowed."""
        principal = _principal()
        intake = _intake(status=IntakeStatus.accepted)
        wi = MagicMock(id=intake.work_item_id, project_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _member(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wi.project_id)

        monkeypatch.setattr(
            "rapidly.projects.intake.actions._readable_work_item", _readable
        )
        monkeypatch.setattr("rapidly.projects.intake.actions._ensure_member", _member)

        with pytest.raises(BadRequest):
            await intake_actions.transition(
                MagicMock(),
                principal,
                intake,
                IntakeWorkItemUpdate(
                    status=IntakeStatus.snoozed,
                    snoozed_until=datetime.now(UTC) + timedelta(days=1),
                ),
            )

    async def test_snooze_requires_future_timestamp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        intake = _intake(status=IntakeStatus.pending)
        wi = MagicMock(id=intake.work_item_id, project_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _member(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wi.project_id)

        monkeypatch.setattr(
            "rapidly.projects.intake.actions._readable_work_item", _readable
        )
        monkeypatch.setattr("rapidly.projects.intake.actions._ensure_member", _member)

        with pytest.raises(BadRequest):
            await intake_actions.transition(
                MagicMock(),
                principal,
                intake,
                IntakeWorkItemUpdate(
                    status=IntakeStatus.snoozed,
                    snoozed_until=datetime.now(UTC) - timedelta(hours=1),
                ),
            )

    async def test_duplicate_requires_target(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        intake = _intake(status=IntakeStatus.pending)
        wi = MagicMock(id=intake.work_item_id, project_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _member(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wi.project_id)

        monkeypatch.setattr(
            "rapidly.projects.intake.actions._readable_work_item", _readable
        )
        monkeypatch.setattr("rapidly.projects.intake.actions._ensure_member", _member)

        with pytest.raises(BadRequest):
            await intake_actions.transition(
                MagicMock(),
                principal,
                intake,
                IntakeWorkItemUpdate(status=IntakeStatus.duplicate),
            )

    async def test_self_duplicate_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        intake = _intake(status=IntakeStatus.pending)
        wi = MagicMock(id=intake.work_item_id, project_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _member(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=wi.project_id)

        monkeypatch.setattr(
            "rapidly.projects.intake.actions._readable_work_item", _readable
        )
        monkeypatch.setattr("rapidly.projects.intake.actions._ensure_member", _member)

        with pytest.raises(BadRequest):
            await intake_actions.transition(
                MagicMock(),
                principal,
                intake,
                IntakeWorkItemUpdate(
                    status=IntakeStatus.duplicate,
                    duplicate_to_id=intake.work_item_id,
                ),
            )
