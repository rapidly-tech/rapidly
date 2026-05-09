"""Tests for ``rapidly/messaging/notification_recipient/queries.py``.

Push-notification device registry. Four load-bearing surfaces:

- ``get_by_expo_token`` looks up by Expo push token (used for
  the de-duplication path: when the SAME device re-registers
  with a different user_id we soft-delete the prior recipient
  before re-creating). Drift to a different column would let
  the same device receive duplicate notifications.
- ``list_by_user`` ALWAYS scopes by ``user_id`` and layers
  optional ``platform`` / ``expo_push_token`` filters on top.
  Drift to drop the user_id filter would leak EVERY user's
  device list to any caller.
- ``delete_for_user`` requires BOTH ``notification_recipient_id``
  AND ``user_id`` to match before soft-deleting. Drift to drop
  the user_id check would let any user delete any other user's
  push-notification device by guessing the recipient UUID.
- ``delete_for_user`` is a SOFT delete (uses ``soft_delete``
  which sets ``deleted_at``) — drift to hard delete would
  cascade-orphan the message-history rows that reference the
  recipient.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from rapidly.messaging.notification_recipient.queries import (
    NotificationRecipientRepository,
)
from rapidly.messaging.notification_recipient.types import (
    NotificationRecipientPlatform,
)


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestGetByExpoToken:
    async def test_query_filters_by_expo_token_column(self) -> None:
        # Pin: lookup keyed on ``expo_push_token``, NOT ``id`` or
        # ``user_id``. Drift would break the de-dup path that
        # soft-deletes prior registrations when a device
        # re-binds to a new user.
        repo = NotificationRecipientRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> object:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.get_by_expo_token("ExponentPushToken[abc]")

        sql = _compile(captured["stmt"]).lower()
        assert "expo_push_token" in sql
        assert "exponentpushtoken[abc]" in sql.lower()


@pytest.mark.asyncio
class TestListByUserPrivacyScope:
    async def _captured(
        self,
        *,
        user_id: UUID,
        platform: NotificationRecipientPlatform | None = None,
        expo_push_token: str | None = None,
    ) -> str:
        repo = NotificationRecipientRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> list[Any]:
            captured["stmt"] = stmt
            return []

        repo.get_all = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        await repo.list_by_user(user_id, platform, expo_push_token)
        return _compile(captured["stmt"]).lower()

    async def test_always_filters_by_user_id(self) -> None:
        # Pin: privacy guard. Drift to drop would leak every
        # user's registered devices to any caller.
        user_id = uuid4()
        sql = await self._captured(user_id=user_id)
        assert "notification_recipients.user_id" in sql
        assert user_id.hex in sql.replace("-", "")

    async def test_no_optional_filters_emits_only_user_filter(self) -> None:
        # Pin: when caller omits platform + token, no extra
        # WHERE clauses are added. Drift to always-filter would
        # silently mismatch on a None platform input.
        sql = await self._captured(user_id=uuid4())
        where_fragment = sql.split("where")[1]
        # The WHERE clause references user_id (and the soft-delete
        # gate from get_base_statement) but NOT platform / token
        # equality predicates.
        assert "platform =" not in where_fragment
        assert "platform in" not in where_fragment
        assert "expo_push_token =" not in where_fragment

    async def test_platform_filter_added_when_provided(self) -> None:
        sql = await self._captured(
            user_id=uuid4(), platform=NotificationRecipientPlatform.ios
        )
        assert "platform" in sql
        assert "'ios'" in sql

    async def test_expo_token_filter_added_when_provided(self) -> None:
        # Pin: optional precise-match filter on the device's Expo
        # push token (used by the registration de-dup helper).
        sql = await self._captured(
            user_id=uuid4(), expo_push_token="ExponentPushToken[abc]"
        )
        assert "expo_push_token" in sql


@pytest.mark.asyncio
class TestDeleteForUserAuthorisation:
    async def test_skips_when_no_matching_recipient(self) -> None:
        # Pin: the helper looks up the row before deleting and
        # NO-OPs when the (id, user_id) pair doesn't match.
        # Drift to delete-without-lookup would let any user
        # destroy any other user's device by guessing the UUID.
        repo = NotificationRecipientRepository(session=MagicMock())
        repo.get_one_or_none = AsyncMock(return_value=None)  # type: ignore[method-assign]
        repo.soft_delete = AsyncMock()  # type: ignore[method-assign]

        await repo.delete_for_user(uuid4(), uuid4())

        repo.soft_delete.assert_not_called()

    async def test_soft_deletes_when_match_found(self) -> None:
        # Pin: when (id, user_id) matches, soft_delete is called.
        # Drift to skip the call would silently leave the
        # recipient active despite the user's "remove device"
        # action.
        repo = NotificationRecipientRepository(session=MagicMock())
        recipient = MagicMock()
        repo.get_one_or_none = AsyncMock(return_value=recipient)  # type: ignore[method-assign]
        repo.soft_delete = AsyncMock()  # type: ignore[method-assign]

        await repo.delete_for_user(uuid4(), uuid4(), flush=True)

        repo.soft_delete.assert_called_once_with(recipient, flush=True)

    async def test_lookup_filters_by_id_AND_user_id(self) -> None:
        # Pin: BOTH id AND user_id MUST be present in the lookup
        # WHERE. Drift to scope by id only would let any user
        # delete any other user's device by guessing the UUID
        # (privacy bug).
        repo = NotificationRecipientRepository(session=MagicMock())
        captured: dict[str, Any] = {}

        async def _capture(stmt: object) -> Any:
            captured["stmt"] = stmt
            return None

        repo.get_one_or_none = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
        repo.soft_delete = AsyncMock()  # type: ignore[method-assign]

        recipient_id = uuid4()
        user_id = uuid4()
        await repo.delete_for_user(recipient_id, user_id)

        sql = _compile(captured["stmt"]).lower()
        # Both UUIDs appear as bound literals in the WHERE.
        assert recipient_id.hex in sql.replace("-", "")
        assert user_id.hex in sql.replace("-", "")
        assert "notification_recipients.id" in sql
        assert "notification_recipients.user_id" in sql
