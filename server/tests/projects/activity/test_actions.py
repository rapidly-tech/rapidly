"""Tests for ``rapidly.projects.activity.actions.emit``.

Pins:
- The emitted row carries the actor's user id when called with a user
  principal — drift here would either log every action as "anonymous"
  (no actor) or attribute system events to a random user.
- Workspace-principal actors leave ``actor_id`` NULL (service tokens
  aren't users; falsely attributing their actions to a user is worse
  than no attribution).
- ``old_value`` / ``new_value`` are stringified and truncated to fit
  the column.  Drift would silently drop long values.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import (
    User,
    WorkItem,
    WorkItemActivity,
    WorkItemActivityVerb,
    WorkItemPriority,
    Workspace,
)
from rapidly.projects.activity import actions as activity_actions


def _work_item() -> WorkItem:
    return WorkItem(
        id=uuid4(),
        project_id=uuid4(),
        sequence_number=1,
        name="x",
        state_id=uuid4(),
        priority=WorkItemPriority.none,
        sort_order=65535.0,
        is_draft=False,
    )


def _user_principal() -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _workspace_principal() -> AuthPrincipal[Workspace]:
    return AuthPrincipal(
        subject=Workspace(id=uuid4(), name="acme", slug="acme"),
        scopes=set(),
        session=None,
    )


def _capturing_session() -> tuple[MagicMock, list[WorkItemActivity]]:
    captured: list[WorkItemActivity] = []
    session = MagicMock()
    session.add = MagicMock(side_effect=lambda row: captured.append(row))
    session.flush = AsyncMock()
    return session, captured


@pytest.mark.asyncio
class TestEmit:
    async def test_user_actor_is_recorded(self) -> None:
        principal = _user_principal()
        work_item = _work_item()
        session, captured = _capturing_session()

        await activity_actions.emit(
            session,
            work_item=work_item,
            actor=principal,
            verb=WorkItemActivityVerb.state_changed,
            field="state_id",
            old_value="a",
            new_value="b",
        )

        assert len(captured) == 1
        row = captured[0]
        assert row.verb == WorkItemActivityVerb.state_changed
        assert row.work_item_id == work_item.id
        assert row.actor_id == principal.subject.id
        assert row.field == "state_id"
        assert row.old_value == "a"
        assert row.new_value == "b"

    async def test_workspace_actor_leaves_actor_null(self) -> None:
        principal = _workspace_principal()
        work_item = _work_item()
        session, captured = _capturing_session()

        await activity_actions.emit(
            session,
            work_item=work_item,
            actor=principal,
            verb=WorkItemActivityVerb.created,
        )

        assert captured[0].actor_id is None

    async def test_no_actor_leaves_actor_null(self) -> None:
        work_item = _work_item()
        session, captured = _capturing_session()

        await activity_actions.emit(
            session,
            work_item=work_item,
            actor=None,
            verb=WorkItemActivityVerb.created,
        )

        assert captured[0].actor_id is None

    async def test_long_values_truncated_to_512(self) -> None:
        principal = _user_principal()
        work_item = _work_item()
        session, captured = _capturing_session()

        long_value = "x" * 2000
        await activity_actions.emit(
            session,
            work_item=work_item,
            actor=principal,
            verb=WorkItemActivityVerb.updated,
            field="description_html",
            old_value=long_value,
            new_value=long_value,
        )

        assert captured[0].old_value is not None
        assert captured[0].new_value is not None
        assert len(captured[0].old_value) == 512
        assert len(captured[0].new_value) == 512

    async def test_non_string_values_are_stringified(self) -> None:
        principal = _user_principal()
        work_item = _work_item()
        session, captured = _capturing_session()

        new_priority = WorkItemPriority.urgent
        await activity_actions.emit(
            session,
            work_item=work_item,
            actor=principal,
            verb=WorkItemActivityVerb.priority_changed,
            field="priority",
            old_value=WorkItemPriority.none,
            new_value=new_priority,
        )

        assert captured[0].old_value == WorkItemPriority.none.value
        assert captured[0].new_value == new_priority.value
