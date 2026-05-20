"""Tests for ``rapidly.projects.recent_visit.actions``.

Invariants pinned:

- ``record`` rejects a foreign workspace (caller-not-a-member).
- ``record`` upserts: existing triplet bumps visited_at; missing triplet inserts.
- The caller is always recorded as ``user_id``; the body has no way to spoof.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import BadRequest
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import RecentVisit, RecentVisitEntityType, User
from rapidly.projects.recent_visit import actions as rv_actions
from rapidly.projects.recent_visit.types import RecentVisitRecord


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _visit(user_id: Any) -> RecentVisit:
    from datetime import UTC, datetime

    return RecentVisit(
        id=uuid4(),
        user_id=user_id,
        workspace_id=uuid4(),
        entity_type=RecentVisitEntityType.project,
        entity_id=uuid4(),
        visited_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
class TestRecord:
    async def test_rejects_foreign_workspace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _not_member(*_a: Any, **_k: Any) -> None:
            raise BadRequest("You are not a member of this workspace.")

        monkeypatch.setattr(
            "rapidly.projects.recent_visit.actions._ensure_workspace_member",
            _not_member,
        )

        with pytest.raises(BadRequest):
            await rv_actions.record(
                MagicMock(),
                principal,
                RecentVisitRecord(
                    workspace_id=uuid4(),
                    entity_type=RecentVisitEntityType.project,
                    entity_id=uuid4(),
                ),
            )

    async def test_bumps_existing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        existing = _visit(principal.subject.id)

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.recent_visit.actions._ensure_workspace_member", _ok
        )

        repo = MagicMock()
        repo.get_for_triplet = AsyncMock(return_value=existing)
        repo.update = AsyncMock(return_value=existing)

        with patch(
            "rapidly.projects.recent_visit.actions.RecentVisitRepository.from_session",
            return_value=repo,
        ):
            await rv_actions.record(
                MagicMock(),
                principal,
                RecentVisitRecord(
                    workspace_id=existing.workspace_id,
                    entity_type=RecentVisitEntityType.project,
                    entity_id=existing.entity_id,
                ),
            )

        assert repo.update.await_count == 1
        _, kwargs = repo.update.call_args
        assert "visited_at" in kwargs["update_dict"]
        # No insert when the row already exists.
        repo.create = getattr(repo, "create", MagicMock())
        if hasattr(repo.create, "assert_not_called"):
            repo.create.assert_not_called()

    async def test_inserts_with_caller_user_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The caller's user_id is the source of truth — never the body."""
        principal = _principal()
        ws_id = uuid4()
        entity_id = uuid4()

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.recent_visit.actions._ensure_workspace_member", _ok
        )

        captured: list[Any] = []
        repo = MagicMock()
        repo.get_for_triplet = AsyncMock(return_value=None)

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.projects.recent_visit.actions.RecentVisitRepository.from_session",
            return_value=repo,
        ):
            await rv_actions.record(
                MagicMock(),
                principal,
                RecentVisitRecord(
                    workspace_id=ws_id,
                    entity_type=RecentVisitEntityType.work_item,
                    entity_id=entity_id,
                ),
            )

        assert captured[0].user_id == principal.subject.id
        assert captured[0].workspace_id == ws_id
        assert captured[0].entity_type == RecentVisitEntityType.work_item
        assert captured[0].entity_id == entity_id
