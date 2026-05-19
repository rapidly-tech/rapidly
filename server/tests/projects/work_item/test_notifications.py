"""Tests for the assignee-notification hook in
``rapidly.projects.work_item.actions``.

Pinned behaviour:

- A notification is sent for each newly-added assignee.
- The actor is never notified about their own self-assignment.
- No notifications are sent when the assignee set is unchanged or empty.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rapidly.identity.auth.models import AuthPrincipal
from rapidly.messaging.notifications.notification import NotificationType
from rapidly.models import User, WorkItem
from rapidly.projects.work_item import actions as wi_actions


def _principal(uid: Any = None) -> AuthPrincipal[User]:
    return AuthPrincipal(
        subject=User(id=uid or uuid4(), email="dev@example.com"),
        scopes=set(),
        session=None,
    )


def _project() -> Any:
    # ``MagicMock(name="Demo")`` sets the mock's debug name, not the
    # attribute — use a configure call so accessing ``.name`` returns
    # the string Pydantic expects.
    project = MagicMock(id=uuid4(), workspace_id=uuid4())
    project.name = "Demo"
    return project


def _work_item(project_id: Any) -> WorkItem:
    return WorkItem(
        id=uuid4(),
        project_id=project_id,
        sequence_number=1,
        name="Wire payments",
    )


@pytest.mark.asyncio
class TestNotifyNewAssignees:
    async def test_notifies_each_new_user(self) -> None:
        actor = _principal()
        project = _project()
        wi = _work_item(project.id)
        a, b = uuid4(), uuid4()
        sends: list[Any] = []

        async def _send(_s: Any, user_id: Any, notif: Any) -> bool:
            sends.append((user_id, notif))
            return True

        with patch(
            "rapidly.projects.work_item.actions.notification_actions.send_to_user",
            _send,
        ):
            await wi_actions._notify_new_assignees(
                MagicMock(),
                work_item=wi,
                project=project,
                actor=actor,
                new_assignee_ids={a, b},
            )

        recipients = {s[0] for s in sends}
        assert recipients == {a, b}
        assert all(s[1].type == NotificationType.work_item_assigned for s in sends)

    async def test_skips_self_assignment(self) -> None:
        """An actor who assigns themselves shouldn't get a notification."""
        actor = _principal()
        project = _project()
        wi = _work_item(project.id)
        sends: list[Any] = []

        async def _send(_s: Any, user_id: Any, notif: Any) -> bool:
            sends.append((user_id, notif))
            return True

        with patch(
            "rapidly.projects.work_item.actions.notification_actions.send_to_user",
            _send,
        ):
            await wi_actions._notify_new_assignees(
                MagicMock(),
                work_item=wi,
                project=project,
                actor=actor,
                new_assignee_ids={actor.subject.id},
            )

        assert sends == []

    async def test_empty_set_is_noop(self) -> None:
        actor = _principal()
        project = _project()
        wi = _work_item(project.id)
        send_mock = AsyncMock(return_value=True)

        with patch(
            "rapidly.projects.work_item.actions.notification_actions.send_to_user",
            send_mock,
        ):
            await wi_actions._notify_new_assignees(
                MagicMock(),
                work_item=wi,
                project=project,
                actor=actor,
                new_assignee_ids=set(),
            )

        send_mock.assert_not_awaited()

    async def test_workspace_principal_treated_as_external_actor(self) -> None:
        """Workspace-scoped tokens don't have a User id; nothing should be
        filtered out as 'self-assignment'."""
        from rapidly.identity.auth.models import Workspace

        actor = AuthPrincipal(
            subject=Workspace(id=uuid4()),
            scopes=set(),
            session=None,
        )
        project = _project()
        wi = _work_item(project.id)
        target = uuid4()
        sends: list[Any] = []

        async def _send(_s: Any, user_id: Any, notif: Any) -> bool:
            sends.append((user_id, notif))
            return True

        with patch(
            "rapidly.projects.work_item.actions.notification_actions.send_to_user",
            _send,
        ):
            await wi_actions._notify_new_assignees(
                MagicMock(),
                work_item=wi,
                project=project,
                actor=actor,
                new_assignee_ids={target},
            )

        assert [s[0] for s in sends] == [target]


@pytest.mark.asyncio
class TestReconcileReturnsDiff:
    async def test_returns_only_newly_added(self) -> None:
        wi_id = uuid4()
        existing = uuid4()
        new = uuid4()

        # Stub session.execute → existing assignee row
        session = MagicMock()
        existing_row = MagicMock(user_id=existing)
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[existing_row]))
                )
            )
        )
        session.add = MagicMock()
        session.flush = AsyncMock()

        result = await wi_actions._reconcile_assignees(session, wi_id, [existing, new])

        assert result == {new}
