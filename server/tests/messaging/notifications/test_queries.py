"""Tests for ``rapidly/messaging/notifications/queries.py``.

Five load-bearing surfaces:

- ``get_by_id`` eager-loads ``user`` (drift to lazy-load would
  N+1 fetch the user row on the notification-detail endpoint).
- ``list_for_user`` scopes by ``user_id`` AND orders by
  ``created_at DESC`` so the newest notifications appear at the
  top of the user's feed. Drift to ASC would bury fresh
  notifications; drift to drop the user_id filter would leak
  every user's notification feed.
- ``list_for_user`` defaults to LIMIT 100 — drift to remove the
  cap could OOM the feed render on power users.
- ``get_user_last_read`` returns None when no row exists (vs.
  raise) so a fresh user's feed renders without crashing.
- ``set_user_last_read`` uses INSERT ... ON CONFLICT DO UPDATE
  on the documented ``(user_id)`` unique index so concurrent
  read-cursor updates don't crash on integrity errors. The
  conflict-update sets only ``last_read_notification_id``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.messaging.notifications.queries import NotificationRepository


def _compile(stmt: object) -> str:
    from sqlalchemy.dialects import postgresql

    return str(
        stmt.compile(  # type: ignore[attr-defined]
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


@pytest.mark.asyncio
class TestGetById:
    async def test_eager_loads_user(self) -> None:
        # Pin: ``joinedload(Notification.user)`` so the detail
        # endpoint doesn't N+1.
        repo = NotificationRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_id(uuid4())

        sql = _compile(captured["stmt"]).lower()
        assert "left outer join users" in sql


@pytest.mark.asyncio
class TestListForUser:
    async def _captured(self, *, limit: int = 100) -> str:
        repo = NotificationRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.list_for_user(uuid4(), limit=limit)
        return _compile(captured["stmt"]).lower()

    async def test_orders_newest_first(self) -> None:
        # Pin: drift to ASC would bury fresh notifications at
        # the bottom of the user's feed.
        sql = await self._captured()
        assert "order by notifications.created_at desc" in sql

    async def test_default_limit_caps_at_100(self) -> None:
        # Pin: drift to remove the cap could OOM on power users.
        sql = await self._captured()
        assert "limit 100" in sql

    async def test_limit_propagates_when_caller_supplies(self) -> None:
        # Pin: caller-supplied limit overrides default.
        sql = await self._captured(limit=10)
        assert "limit 10" in sql

    async def test_scopes_by_user_id(self) -> None:
        # Pin: privacy guard. Drift to drop the user_id filter
        # would leak every user's notification feed.
        repo = NotificationRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        target = uuid4()
        await repo.list_for_user(target)

        sql = _compile(captured["stmt"]).replace("-", "")
        assert target.hex in sql


@pytest.mark.asyncio
class TestReadCursor:
    async def test_get_user_last_read_returns_none_for_no_row(self) -> None:
        # Pin: a fresh user's feed renders without crashing.
        repo = NotificationRepository(session=MagicMock())
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        repo.session.execute = AsyncMock(return_value=result)  # type: ignore[method-assign]

        out = await repo.get_user_last_read(uuid4())
        assert out is None

    async def test_get_user_last_read_returns_id_when_row_exists(self) -> None:
        repo = NotificationRepository(session=MagicMock())
        notification_id = uuid4()
        row = MagicMock()
        row.last_read_notification_id = notification_id

        result = MagicMock()
        result.scalar_one_or_none.return_value = row
        repo.session.execute = AsyncMock(return_value=result)  # type: ignore[method-assign]

        out = await repo.get_user_last_read(uuid4())
        assert out == notification_id

    async def test_set_user_last_read_uses_upsert_on_user_id(self) -> None:
        # Pin: INSERT ... ON CONFLICT DO UPDATE on (user_id) so
        # concurrent updates don't crash on integrity errors.
        # Drift to plain INSERT would 500 on every cursor
        # advance after the first.
        repo = NotificationRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _exec(stmt: object) -> Any:
            captured["stmt"] = stmt
            return MagicMock()

        repo.session.execute = AsyncMock(side_effect=_exec)  # type: ignore[method-assign]

        target_user = uuid4()
        target_notification = uuid4()
        await repo.set_user_last_read(target_user, target_notification)

        sql = _compile(captured["stmt"]).lower()
        assert sql.startswith("insert into user_notifications")
        assert "on conflict" in sql
        assert "do update" in sql
        # The conflict target is the user_id index.
        assert "user_id" in sql
        # The update sets only the last_read_notification_id field.
        assert "last_read_notification_id" in sql
