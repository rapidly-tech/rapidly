"""Tests for ``rapidly/messaging/notifications/workers/push.py``.

Expo push notification dispatch. Three load-bearing surfaces:

- ``send_push_message`` constructs a ``PushMessage`` with pinned
  options: title="Rapidly", sound="default", priority="high",
  ttl=86400 (1 day), badge=1, channel_id="default". Drift would
  break iOS/Android-specific push behaviour silently (e.g.,
  wrong category → notification doesn't trigger the action set).
- All push errors (PushServerError, DeviceNotRegisteredError,
  generic Exception) RAISE after logging — the caller's retry
  middleware needs to see them; drift to silent-swallow would
  hide systemic Expo outages.
- ``notifications_push`` actor handles edge cases gracefully:
  missing notification, no recipients, recipient without push
  token. Send-failure on one recipient logs + returns early
  (NOT raises) so the actor doesn't enter the dead-letter queue
  on transient device errors.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.messaging.notifications.workers import push as M
from rapidly.messaging.notifications.workers.push import (
    notifications_push,
    send_push_message,
)


class TestSendPushMessage:
    def test_constructs_push_message_with_pinned_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: PushMessage carries the documented options.
        # title="Rapidly" labels the notification source on the
        # device; sound/priority/badge match Apple/Google
        # platform conventions.
        captured: dict[str, Any] = {}

        def fake_publish(msg: Any) -> Any:
            captured["msg"] = msg
            response = MagicMock()
            response.validate_response = MagicMock()
            return response

        monkeypatch.setattr(M._push_client, "publish", fake_publish)

        send_push_message(token="ExpoPushToken[abc]", message="Hello!")

        msg = captured["msg"]
        assert msg.title == "Rapidly"
        assert msg.sound == "default"
        assert msg.priority == "high"
        assert msg.ttl == 86400
        assert msg.badge == 1
        assert msg.channel_id == "default"
        assert msg.body == "Hello!"
        assert msg.to == "ExpoPushToken[abc]"

    def test_validate_response_called_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: response validation runs after publish so a soft
        # error (e.g., DeviceNotRegistered in the response body)
        # surfaces as an exception. Drift would silently consider
        # every publish "successful".
        validate_called: list[bool] = []

        def fake_publish(msg: Any) -> Any:
            response = MagicMock()
            response.validate_response = MagicMock(
                side_effect=lambda: validate_called.append(True)
            )
            return response

        monkeypatch.setattr(M._push_client, "publish", fake_publish)
        send_push_message(token="t", message="m")
        assert validate_called == [True]

    def test_push_server_error_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: PushServerError raises after logging. Caller's
        # retry middleware needs to see it.
        from exponent_server_sdk import PushServerError

        def fake_publish(msg: Any) -> Any:
            raise PushServerError("Expo down", response=None)

        monkeypatch.setattr(M._push_client, "publish", fake_publish)

        with pytest.raises(PushServerError):
            send_push_message(token="t", message="m")

    def test_device_not_registered_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: DeviceNotRegisteredError raises so the actor can
        # mark the token as stale (token-cleanup workflow).
        from exponent_server_sdk import DeviceNotRegisteredError

        # The exact constructor signature varies by exponent-server-sdk
        # version; raise via __new__ to bypass __init__.
        instance = DeviceNotRegisteredError.__new__(DeviceNotRegisteredError)

        def fake_publish(msg: Any) -> Any:
            raise instance

        monkeypatch.setattr(M._push_client, "publish", fake_publish)

        with pytest.raises(DeviceNotRegisteredError):
            send_push_message(token="t", message="m")

    def test_generic_exception_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: unexpected exceptions also raise (after logging).
        # Drift to silent-swallow would hide systemic Expo
        # outages.
        def fake_publish(msg: Any) -> Any:
            raise RuntimeError("network down")

        monkeypatch.setattr(M._push_client, "publish", fake_publish)

        with pytest.raises(RuntimeError, match="network down"):
            send_push_message(token="t", message="m")

    def test_validate_response_failure_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: validate_response failures raise (NOT silently
        # logged). Otherwise an Expo policy violation on a single
        # publish would never surface.
        def fake_publish(msg: Any) -> Any:
            response = MagicMock()
            response.validate_response = MagicMock(
                side_effect=ValueError("invalid response")
            )
            return response

        monkeypatch.setattr(M._push_client, "publish", fake_publish)

        with pytest.raises(ValueError, match="invalid response"):
            send_push_message(token="t", message="m")


def _patch_session(
    monkeypatch: pytest.MonkeyPatch,
    *,
    notif: Any | None,
    recipients: list[Any] | None = None,
) -> None:
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=MagicMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

    fake_notifications = MagicMock()
    fake_notifications.get = AsyncMock(return_value=notif)

    notification_type = MagicMock()
    notification_type.render = MagicMock(return_value=("Subject", "<body/>"))
    fake_notifications.parse_payload = MagicMock(return_value=notification_type)
    monkeypatch.setattr(M, "notifications", fake_notifications)

    fake_recipient_service = MagicMock()
    fake_recipient_service.list_by_user = AsyncMock(
        return_value=recipients if recipients is not None else []
    )
    monkeypatch.setattr(M, "notification_recipient_service", fake_recipient_service)


@pytest.mark.asyncio
class TestNotificationsPushActor:
    async def test_missing_notification_logs_and_returns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: missing notification → return (NOT raise). Same
        # late-arrival rationale as the email actor.
        _patch_session(monkeypatch, notif=None)
        sent: list[bool] = []
        monkeypatch.setattr(M, "send_push_message", lambda **kw: sent.append(True))
        result = await notifications_push.__wrapped__(  # type: ignore[attr-defined]
            notification_id=uuid4()
        )
        assert result is None
        assert sent == []

    async def test_no_recipients_logs_and_returns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: empty recipients list → return. A user without
        # any registered devices is normal (web-only users) and
        # must NOT crash the actor.
        notif = MagicMock()
        notif.user_id = uuid4()
        _patch_session(monkeypatch, notif=notif, recipients=[])

        sent: list[bool] = []
        monkeypatch.setattr(M, "send_push_message", lambda **kw: sent.append(True))
        await notifications_push.__wrapped__(  # type: ignore[attr-defined]
            notification_id=uuid4()
        )
        assert sent == []

    async def test_recipient_without_push_token_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a recipient row without ``expo_push_token`` is
        # skipped (continue). Other recipients still get pushed.
        notif = MagicMock()
        notif.user_id = uuid4()

        no_token = MagicMock()
        no_token.expo_push_token = None
        no_token.user_id = uuid4()

        with_token = MagicMock()
        with_token.expo_push_token = "ExpoPushToken[ok]"
        with_token.user_id = uuid4()

        _patch_session(monkeypatch, notif=notif, recipients=[no_token, with_token])
        sent: list[str] = []
        monkeypatch.setattr(
            M,
            "send_push_message",
            lambda **kw: sent.append(kw["token"]),
        )
        await notifications_push.__wrapped__(  # type: ignore[attr-defined]
            notification_id=uuid4()
        )
        # Only the token-bearing recipient was sent to.
        assert sent == ["ExpoPushToken[ok]"]

    async def test_send_failure_logs_and_returns_early(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a single recipient's send-failure is LOGGED + the
        # actor returns early (NOT raises). Otherwise a single
        # bad device would push the entire notification into the
        # dead-letter queue.
        notif = MagicMock()
        notif.user_id = uuid4()

        bad = MagicMock()
        bad.expo_push_token = "ExpoPushToken[bad]"
        bad.user_id = uuid4()

        _patch_session(monkeypatch, notif=notif, recipients=[bad])

        def boom(**kw: Any) -> None:
            raise RuntimeError("device down")

        monkeypatch.setattr(M, "send_push_message", boom)

        # Note: NOT pytest.raises — the actor swallows.
        result = await notifications_push.__wrapped__(  # type: ignore[attr-defined]
            notification_id=uuid4()
        )
        assert result is None

    async def test_extra_carries_notification_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``extra={"notification_id": str(notification_id)}``
        # so the mobile app can deep-link from the push
        # notification back to the in-app row. Drift would break
        # the deep-link.
        notif = MagicMock()
        notif.user_id = uuid4()

        recipient = MagicMock()
        recipient.expo_push_token = "ExpoPushToken[ok]"
        recipient.user_id = uuid4()

        _patch_session(monkeypatch, notif=notif, recipients=[recipient])

        captured: dict[str, Any] = {}
        monkeypatch.setattr(M, "send_push_message", lambda **kw: captured.update(kw))

        nid = uuid4()
        await notifications_push.__wrapped__(  # type: ignore[attr-defined]
            notification_id=nid
        )
        assert captured["extra"] == {"notification_id": str(nid)}
