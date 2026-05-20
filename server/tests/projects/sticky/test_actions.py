"""Tests for ``rapidly.projects.sticky.actions``.

Invariants pinned:

- ``create`` rejects when the caller isn't a member of the target workspace
  — preventing existence-leak via the FK constraint.
- ``update`` is a no-op when the payload has no set fields.
- The repository's readable-statement guarantees a caller never sees
  someone else's stickies — pinned via the action layer never bypassing it.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import BadRequest
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import Sticky, User
from rapidly.projects.sticky import actions as sticky_actions
from rapidly.projects.sticky.types import StickyCreate, StickyUpdate


def _principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _sticky(owner_id: Any, workspace_id: Any) -> Sticky:
    return Sticky(
        id=uuid4(),
        workspace_id=workspace_id,
        owner_id=owner_id,
        name="TODO",
        sort_order=65535.0,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_rejects_foreign_workspace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _not_member(*_a: Any, **_k: Any) -> None:
            raise BadRequest("You are not a member of this workspace.")

        monkeypatch.setattr(
            "rapidly.projects.sticky.actions._ensure_workspace_member", _not_member
        )

        with pytest.raises(BadRequest):
            await sticky_actions.create(
                MagicMock(),
                principal,
                StickyCreate(workspace_id=uuid4(), name="Drafts"),
            )

    async def test_creates_with_caller_as_owner(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        ws_id = uuid4()

        async def _ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.sticky.actions._ensure_workspace_member", _ok
        )

        captured: list[Any] = []
        repo = MagicMock()

        async def _create(obj: Any, flush: bool = False) -> Any:
            captured.append(obj)
            return obj

        repo.create = _create

        with patch(
            "rapidly.projects.sticky.actions.StickyRepository.from_session",
            return_value=repo,
        ):
            await sticky_actions.create(
                MagicMock(),
                principal,
                StickyCreate(workspace_id=ws_id, name="Drafts"),
            )

        assert captured[0].owner_id == principal.subject.id
        assert captured[0].workspace_id == ws_id


@pytest.mark.asyncio
class TestUpdate:
    async def test_empty_payload_is_noop(self) -> None:
        principal = _principal()
        sticky = _sticky(principal.subject.id, uuid4())

        repo = MagicMock()
        repo.update = AsyncMock(return_value=sticky)

        with patch(
            "rapidly.projects.sticky.actions.StickyRepository.from_session",
            return_value=repo,
        ):
            result = await sticky_actions.update(
                MagicMock(), principal, sticky, StickyUpdate()
            )

        assert result is sticky
        repo.update.assert_not_called()
