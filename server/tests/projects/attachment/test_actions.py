"""Tests for ``rapidly.projects.attachment.actions``.

Invariants pinned:

- ``create`` requires read access to the work item.
- ``create`` requires the ``member`` project role.
- ``create`` rejects a file from a different workspace (cross-workspace attach).
- ``create`` rejects duplicate (work_item_id, file_id) pairs.
- ``delete`` requires the ``member`` project role.
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
from rapidly.models import User, WorkItemAttachment
from rapidly.projects.attachment import actions as att_actions
from rapidly.projects.attachment.types import WorkItemAttachmentCreate


def _principal(uid: Any = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uid or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _attachment() -> WorkItemAttachment:
    return WorkItemAttachment(
        id=uuid4(), work_item_id=uuid4(), file_id=uuid4(), uploaded_by_id=None
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_unreadable_work_item_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()

        async def _unreadable(*_a: Any, **_k: Any) -> Any:
            raise ResourceNotFound()

        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._readable_work_item", _unreadable
        )

        with pytest.raises(ResourceNotFound):
            await att_actions.create(
                MagicMock(),
                principal,
                WorkItemAttachmentCreate(work_item_id=uuid4(), file_id=uuid4()),
            )

    async def test_role_gate_member_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        principal = _principal()
        wi = MagicMock(id=uuid4(), project_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._readable_work_item", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._ensure_member", _ensure
        )

        with pytest.raises(NotPermitted):
            await att_actions.create(
                MagicMock(),
                principal,
                WorkItemAttachmentCreate(work_item_id=wi.id, file_id=uuid4()),
            )

    async def test_cross_workspace_file_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pin: a file from a foreign workspace must NOT be attachable."""
        principal = _principal()
        wi = MagicMock(id=uuid4(), project_id=uuid4())
        project = MagicMock(id=wi.project_id, workspace_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        async def _cross_workspace(*_a: Any, **_k: Any) -> None:
            raise BadRequest("File does not belong to this workspace.")

        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._readable_work_item", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._ensure_member", _ensure
        )
        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._ensure_file_in_workspace",
            _cross_workspace,
        )

        with pytest.raises(BadRequest):
            await att_actions.create(
                MagicMock(),
                principal,
                WorkItemAttachmentCreate(work_item_id=wi.id, file_id=uuid4()),
            )

    async def test_duplicate_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        wi = MagicMock(id=uuid4(), project_id=uuid4())
        project = MagicMock(id=wi.project_id, workspace_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            return project

        async def _file_ok(*_a: Any, **_k: Any) -> None:
            return None

        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._readable_work_item", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._ensure_member", _ensure
        )
        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._ensure_file_in_workspace",
            _file_ok,
        )

        repo = MagicMock()
        repo.get_one_or_none = AsyncMock(return_value=_attachment())

        with patch(
            "rapidly.projects.attachment.actions.WorkItemAttachmentRepository.from_session",
            return_value=repo,
        ):
            with pytest.raises(ResourceAlreadyExists):
                await att_actions.create(
                    MagicMock(),
                    principal,
                    WorkItemAttachmentCreate(work_item_id=wi.id, file_id=uuid4()),
                )


@pytest.mark.asyncio
class TestDelete:
    async def test_requires_member_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        principal = _principal()
        attachment = _attachment()
        wi = MagicMock(id=attachment.work_item_id, project_id=uuid4())

        async def _readable(*_a: Any, **_k: Any) -> Any:
            return wi

        async def _ensure(*_a: Any, **_k: Any) -> Any:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._readable_work_item", _readable
        )
        monkeypatch.setattr(
            "rapidly.projects.attachment.actions._ensure_member", _ensure
        )

        with pytest.raises(NotPermitted):
            await att_actions.delete(MagicMock(), principal, attachment)
