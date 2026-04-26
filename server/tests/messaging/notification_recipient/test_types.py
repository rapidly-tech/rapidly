"""Tests for ``rapidly/messaging/notification_recipient/types.py``.

The ``NotificationRecipientPlatform`` enum is the dispatch key the
push-notification worker uses to pick between the iOS and Android
push providers. Adding a third platform value without wiring it
through the worker would silently drop notifications for that
platform; renaming an existing value would break on-device tokens
already persisted.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rapidly.messaging.notification_recipient.types import (
    NotificationRecipientCreate,
    NotificationRecipientPlatform,
)


class TestNotificationRecipientPlatform:
    def test_exposes_exactly_ios_and_android(self) -> None:
        # The set must be pinned — worker dispatch keys off this enum.
        # A silent third member (e.g. ``web``) would reach the worker
        # without a dispatch branch and fall through without sending.
        assert {e.value for e in NotificationRecipientPlatform} == {"ios", "android"}

    def test_values_match_wire_strings(self) -> None:
        # Mobile clients send the string literally; attribute-renames
        # don't break the wire.
        assert NotificationRecipientPlatform.ios == "ios"
        assert NotificationRecipientPlatform.android == "android"


class TestNotificationRecipientCreate:
    def test_requires_platform_and_token(self) -> None:
        with pytest.raises(ValidationError):
            NotificationRecipientCreate.model_validate({"platform": "ios"})
        with pytest.raises(ValidationError):
            NotificationRecipientCreate.model_validate({"expo_push_token": "tk"})

    def test_rejects_unknown_platform(self) -> None:
        with pytest.raises(ValidationError):
            NotificationRecipientCreate.model_validate(
                {"platform": "windows", "expo_push_token": "tk"}
            )

    def test_does_not_accept_user_id_from_caller(self) -> None:
        # Subject identity MUST come from the authenticated principal,
        # never the request body. Pinning the absence of a ``user_id``
        # field on Create prevents a regression that would let a
        # caller register a push token under someone else's user id.
        assert "user_id" not in NotificationRecipientCreate.model_fields

    def test_accepts_valid_body(self) -> None:
        body = NotificationRecipientCreate(
            platform=NotificationRecipientPlatform.ios,
            expo_push_token="ExpoPushToken[x]",
        )
        assert body.platform == NotificationRecipientPlatform.ios
        assert body.expo_push_token == "ExpoPushToken[x]"
