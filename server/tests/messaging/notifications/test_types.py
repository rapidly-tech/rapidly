"""Tests for ``rapidly/messaging/notifications/types.py``.

Small schema but a meaningful pin: ``NotificationsMarkRead`` must
require a UUID4 for the ``notification_id``. A regression accepting
arbitrary strings would let a caller mark-as-read arbitrary rows by
guessing the format, and would be a latent shape mismatch with the
query layer.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.messaging.notifications.types import (
    NotificationsList,
    NotificationsMarkRead,
)


class TestNotificationsMarkRead:
    def test_requires_uuid4(self) -> None:
        # UUID4 is what the ORM primary key uses. A malformed id
        # must fail at validation — not at the ``WHERE id = ...``
        # clause downstream.
        with pytest.raises(ValidationError):
            NotificationsMarkRead(notification_id="not-a-uuid")  # type: ignore[arg-type]

    def test_accepts_valid_uuid(self) -> None:
        body = NotificationsMarkRead(
            notification_id="550e8400-e29b-41d4-a716-446655440000"  # type: ignore[arg-type]
        )
        assert str(body.notification_id) == "550e8400-e29b-41d4-a716-446655440000"


class TestNotificationsList:
    def test_accepts_null_last_read(self) -> None:
        # A user who has never marked anything read — last_read must
        # be nullable, not absent. Regression that made this required
        # would 500 every /notifications list call for new users.
        body = NotificationsList(notifications=[], last_read_notification_id=None)
        assert body.last_read_notification_id is None
        assert body.notifications == []
