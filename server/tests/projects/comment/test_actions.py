"""Tests for ``rapidly.projects.comment.actions``.

Key invariants:

- ``create`` requires the parent work item to be readable, the project
  to be resolvable, and the caller to hold at least ``member`` role.
- ``update`` and ``delete`` are **author-only** for user principals.
  A different user (even a project member) is rejected unless they
  hold the ``admin`` project role.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from rapidly.errors import NotPermitted
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import ProjectMemberRole, User, WorkItem, WorkItemComment
from rapidly.projects.comment import actions as comment_actions
from rapidly.projects.comment.types import (
    WorkItemCommentCreate,
    WorkItemCommentUpdate,
)


def _user_principal(user_id: UUID | None = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=user_id or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _work_item(project_id: UUID | None = None) -> WorkItem:
    from rapidly.models import WorkItemPriority

    return WorkItem(
        id=uuid4(),
        project_id=project_id or uuid4(),
        sequence_number=1,
        name="x",
        state_id=uuid4(),
        priority=WorkItemPriority.none,
        sort_order=65535.0,
        is_draft=False,
    )


def _comment(
    work_item_id: UUID | None = None, actor_id: UUID | None = None
) -> WorkItemComment:
    return WorkItemComment(
        id=uuid4(),
        work_item_id=work_item_id or uuid4(),
        actor_id=actor_id or uuid4(),
        body_html="<p>hi</p>",
    )


def _patch_setup(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> None:
    """Default mocks for ``_readable_work_item`` and ``_project_for_work_item``."""
    work_item = overrides.get("work_item", _work_item())
    project = overrides.get(
        "project",
        MagicMock(id=work_item.project_id, workspace_id=uuid4(), owner_id=uuid4()),
    )

    async def _wi(*_a: Any, **_k: Any) -> WorkItem:
        return work_item

    async def _proj(*_a: Any, **_k: Any) -> Any:
        return project

    monkeypatch.setattr("rapidly.projects.comment.actions._readable_work_item", _wi)
    monkeypatch.setattr(
        "rapidly.projects.comment.actions._project_for_work_item", _proj
    )


@pytest.mark.asyncio
class TestCreate:
    async def test_role_gate_member_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a workspace member without a project role cannot post.
        principal = _user_principal()
        _patch_setup(monkeypatch)

        session = MagicMock()
        with patch(
            "rapidly.projects.comment.actions.require_role",
            side_effect=NotPermitted(),
        ) as gate:
            with pytest.raises(NotPermitted):
                await comment_actions.create(
                    session,
                    principal,
                    WorkItemCommentCreate(work_item_id=uuid4(), body_html="<p>hi</p>"),
                )
            assert gate.await_args is not None
            assert gate.await_args.kwargs["minimum"] == ProjectMemberRole.member


@pytest.mark.asyncio
class TestUpdate:
    async def test_author_can_edit_own_comment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a user can always edit their own comment without an
        # admin check.  Drift would block users from fixing typos.
        author_id = uuid4()
        principal = _user_principal(author_id)
        comment = _comment(actor_id=author_id)

        session = MagicMock()
        repo = MagicMock()
        repo.update = AsyncMock(return_value=comment)

        ensure_admin = AsyncMock()
        monkeypatch.setattr(
            "rapidly.projects.comment.actions._ensure_admin_for_comment",
            ensure_admin,
        )

        with patch(
            "rapidly.projects.comment.actions.WorkItemCommentRepository.from_session",
            return_value=repo,
        ):
            await comment_actions.update(
                session, principal, comment, WorkItemCommentUpdate(body_html="edited")
            )
        ensure_admin.assert_not_called()
        repo.update.assert_awaited_once()

    async def test_non_author_blocked_unless_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a different user cannot edit someone else's comment
        # without holding the admin project role.
        principal = _user_principal(uuid4())  # not the author
        comment = _comment(actor_id=uuid4())

        session = MagicMock()

        async def _admin(*_a: Any, **_k: Any) -> None:
            raise NotPermitted()

        monkeypatch.setattr(
            "rapidly.projects.comment.actions._ensure_admin_for_comment", _admin
        )

        with pytest.raises(NotPermitted):
            await comment_actions.update(
                session, principal, comment, WorkItemCommentUpdate(body_html="x")
            )


@pytest.mark.asyncio
class TestDelete:
    async def test_author_can_delete_own_comment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        author_id = uuid4()
        principal = _user_principal(author_id)
        comment = _comment(actor_id=author_id)

        session = MagicMock()
        repo = MagicMock()
        repo.soft_delete = AsyncMock(return_value=comment)

        monkeypatch.setattr(
            "rapidly.projects.comment.actions._ensure_admin_for_comment", AsyncMock()
        )

        with patch(
            "rapidly.projects.comment.actions.WorkItemCommentRepository.from_session",
            return_value=repo,
        ):
            await comment_actions.delete(session, principal, comment)
        repo.soft_delete.assert_awaited_once_with(comment)


@pytest.mark.asyncio
class TestGet:
    async def test_unknown_returns_none(self) -> None:
        principal = _user_principal()
        session = MagicMock()

        repo = MagicMock()
        repo.get_readable_statement = MagicMock(return_value=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=None)

        with patch(
            "rapidly.projects.comment.actions.WorkItemCommentRepository.from_session",
            return_value=repo,
        ):
            assert await comment_actions.get(session, principal, uuid4()) is None
