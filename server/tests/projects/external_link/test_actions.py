"""Tests for ``rapidly.projects.external_link.actions``.

Invariants pinned:

- ``create`` requires the caller to have read access to the work item.
- ``create`` requires the ``member`` project role.
- ``update`` and ``delete`` require the ``member`` project role.
- ``update`` allows clearing the title back to NULL without clearing the URL.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.errors import NotPermitted, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import User, WorkItemLink
from rapidly.projects.external_link import actions as link_actions
from rapidly.projects.external_link.types import (
    WorkItemLinkCreate,
    WorkItemLinkUpdate,
)


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _link(title: str | None = "Figma") -> WorkItemLink:
    return WorkItemLink(
        id=uuid4(),
        work_item_id=uuid4(),
        url="https://figma.com/x",
        title=title,
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_rejects_unreadable_work_item(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()

        async def _unreadable(*_a: Any, **_k: Any) -> Any:
            raise ResourceNotFound("Work item not found.")

        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._readable_work_item", _unreadable
        )

        with pytest.raises(ResourceNotFound):
            await link_actions.create(
                session,
                principal,
                WorkItemLinkCreate(
                    work_item_id=uuid4(),
                    url="https://figma.com/x",  # type: ignore[arg-type]
                ),
            )

    async def test_role_gate_member_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        session = MagicMock()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=uuid4(), project_id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._readable_work_item", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._ensure_member", _ensure
        )

        with pytest.raises(NotPermitted):
            await link_actions.create(
                session,
                principal,
                WorkItemLinkCreate(
                    work_item_id=uuid4(),
                    url="https://figma.com/x",  # type: ignore[arg-type]
                ),
            )


@pytest.mark.asyncio
class TestUpdateDelete:
    async def test_update_requires_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        link = _link()
        session = MagicMock()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=uuid4(), project_id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._readable_work_item", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._ensure_member", _ensure
        )

        with pytest.raises(NotPermitted):
            await link_actions.update(
                session,
                principal,
                link,
                WorkItemLinkUpdate(title="renamed"),
            )

    async def test_delete_requires_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        link = _link()
        session = MagicMock()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=uuid4(), project_id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._readable_work_item", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._ensure_member", _ensure
        )

        with pytest.raises(NotPermitted):
            await link_actions.delete(session, principal, link)

    async def test_update_can_clear_title_to_null(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``title=None`` in the payload must persist as NULL, not be ignored."""
        principal = _user_principal()
        link = _link(title="Old")
        session = MagicMock()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=uuid4(), project_id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._readable_work_item", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._ensure_member", _ensure
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=link)

        with patch(
            "rapidly.projects.external_link.actions.WorkItemLinkRepository.from_session",
            return_value=repo,
        ):
            await link_actions.update(
                session,
                principal,
                link,
                WorkItemLinkUpdate(title=None),
            )

        assert repo.update.await_count == 1
        _, kwargs = repo.update.call_args
        assert kwargs["update_dict"] == {"title": None}

    async def test_update_noop_when_no_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _user_principal()
        link = _link()
        session = MagicMock()

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return MagicMock(id=uuid4(), project_id=uuid4())

        async def _ensure(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._readable_work_item", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.external_link.actions._ensure_member", _ensure
        )

        repo = MagicMock()
        repo.update = AsyncMock(return_value=link)

        with patch(
            "rapidly.projects.external_link.actions.WorkItemLinkRepository.from_session",
            return_value=repo,
        ):
            result = await link_actions.update(
                session, principal, link, WorkItemLinkUpdate()
            )

        assert result is link
        repo.update.assert_not_called()
