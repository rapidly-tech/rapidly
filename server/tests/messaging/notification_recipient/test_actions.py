"""Tests for ``rapidly/messaging/notification_recipient/actions.py``.

Three load-bearing surfaces:

- ``create`` rejects a duplicate Expo push token with a
  ``RequestValidationError`` BEFORE persisting. Drift to skip
  the check would let the same device row appear twice in the
  recipient list and double-deliver every push notification.
- ``create`` binds the new recipient's ``user_id`` from the
  authenticated principal (NOT a request-body field). Drift to
  trust a body field would let any authenticated user register
  a push token under another user's id (cross-user device
  hijack — silent push-takeover).
- ``delete`` forwards the principal's user_id to
  ``delete_for_user`` so the repository can enforce its
  privacy guard (id + user_id WHERE). Drift to forward a
  different id would let any authenticated user delete any
  other user's push device.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.errors import RequestValidationError
from rapidly.messaging.notification_recipient import actions
from rapidly.messaging.notification_recipient.types import (
    NotificationRecipientCreate,
    NotificationRecipientPlatform,
)


def _principal(user_id: Any = None) -> Any:
    p = MagicMock()
    p.subject = MagicMock()
    p.subject.id = user_id or uuid4()
    return p


@pytest.fixture
def repo_patch(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace the repo factory so we can introspect calls."""
    repo = MagicMock()
    repo.list_by_user = AsyncMock(return_value=[])
    repo.get_by_expo_token = AsyncMock(return_value=None)
    repo.create = AsyncMock(side_effect=lambda obj, flush=False: obj)
    repo.delete_for_user = AsyncMock()

    monkeypatch.setattr(
        "rapidly.messaging.notification_recipient.actions"
        ".NotificationRecipientRepository.from_session",
        MagicMock(return_value=repo),
    )
    return repo


@pytest.mark.asyncio
class TestCreateDuplicateRejection:
    async def test_existing_token_raises_request_validation_error(
        self, repo_patch: MagicMock
    ) -> None:
        # Pin: duplicate-token check uses ``get_by_expo_token``
        # and raises ``RequestValidationError`` BEFORE create().
        # Drift would let the same device row appear twice in
        # the recipient list and double-deliver every push.
        repo_patch.get_by_expo_token.return_value = MagicMock()  # existing row

        body = NotificationRecipientCreate(
            platform=NotificationRecipientPlatform.ios,
            expo_push_token="ExponentPushToken[abc]",
        )

        with pytest.raises(RequestValidationError):
            await actions.create(MagicMock(), body, _principal())

        # And no create call was made.
        repo_patch.create.assert_not_called()

    async def test_no_existing_token_calls_create(self, repo_patch: MagicMock) -> None:
        # Pin: clean path goes through to repository.create.
        repo_patch.get_by_expo_token.return_value = None

        body = NotificationRecipientCreate(
            platform=NotificationRecipientPlatform.ios,
            expo_push_token="ExponentPushToken[xyz]",
        )

        await actions.create(MagicMock(), body, _principal())

        repo_patch.create.assert_called_once()


@pytest.mark.asyncio
class TestCreateBindsAuthSubjectUserId:
    async def test_user_id_from_principal_not_body(self, repo_patch: MagicMock) -> None:
        # Pin: ``user_id`` is taken from the authenticated
        # principal, not the request body. Drift to trust a body
        # field would let any authenticated user register a push
        # token UNDER ANOTHER USER'S id — silent push-takeover.
        my_id = uuid4()
        principal = _principal(user_id=my_id)

        body = NotificationRecipientCreate(
            platform=NotificationRecipientPlatform.android,
            expo_push_token="ExponentPushToken[abc]",
        )

        await actions.create(MagicMock(), body, principal)

        # Inspect the persisted object.
        recipient = repo_patch.create.call_args.args[0]
        assert recipient.user_id == my_id


@pytest.mark.asyncio
class TestDeleteForwardsAuthUserId:
    async def test_delete_forwards_principal_user_id_to_repo(
        self, repo_patch: MagicMock
    ) -> None:
        # Pin: privacy guard. The repo's ``delete_for_user`` uses
        # the user_id in its WHERE — drift to forward a different
        # id would let any user delete any other user's device.
        my_id = uuid4()
        principal = _principal(user_id=my_id)
        recipient_id = uuid4()

        await actions.delete(MagicMock(), principal, recipient_id)

        repo_patch.delete_for_user.assert_called_once_with(recipient_id, my_id)


@pytest.mark.asyncio
class TestListByUserForwardsFilters:
    async def test_forwards_user_id_token_and_platform(
        self, repo_patch: MagicMock
    ) -> None:
        # Pin: action layer is a thin pass-through to the repo's
        # ``list_by_user`` method — drift to swap arg order or
        # drop a kwarg would silently widen results (e.g.,
        # listing ALL platforms when caller asked for ios only).
        my_id = uuid4()
        await actions.list_by_user(
            MagicMock(),
            my_id,
            "ExponentPushToken[abc]",
            NotificationRecipientPlatform.ios,
        )

        repo_patch.list_by_user.assert_called_once_with(
            my_id,
            expo_push_token="ExponentPushToken[abc]",
            platform=NotificationRecipientPlatform.ios,
        )
