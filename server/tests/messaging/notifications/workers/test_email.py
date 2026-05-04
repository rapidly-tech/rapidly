"""Tests for ``rapidly/messaging/notifications/workers/email.py``.

Notification → email-send dispatch actor. Two load-bearing surfaces:

- Missing notification (looked up by id) → log warning + RETURN
  (NOT raise). Drift to raising would put every late-arriving
  notification (created→dispatch race) into the dead-letter queue.
- Successful dispatch: parse payload, render to (subject, html),
  ``enqueue_email`` with ``notif.user.email``. Drift in the
  delegation would silently drop notification emails.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.messaging.notifications.workers import email as M
from rapidly.messaging.notifications.workers.email import notifications_send


def _patch_session(monkeypatch: pytest.MonkeyPatch, *, notif: Any | None) -> Any:
    """Patch AsyncSessionMaker + notifications.get."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=MagicMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

    fake_notifications = MagicMock()
    fake_notifications.get = AsyncMock(return_value=notif)
    fake_notifications.parse_payload = MagicMock()
    monkeypatch.setattr(M, "notifications", fake_notifications)
    return fake_notifications


@pytest.mark.asyncio
class TestNotificationsSend:
    async def test_missing_notification_logs_and_returns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: missing notification → log warning + return (NOT raise).
        # A late-arriving notification (created→dispatch race) must
        # NOT enter the dead-letter queue.
        _patch_session(monkeypatch, notif=None)
        # ``enqueue_email`` should NOT be called.
        called: list[bool] = []
        monkeypatch.setattr(M, "enqueue_email", lambda **kw: called.append(True))

        result = await notifications_send.__wrapped__(  # type: ignore[attr-defined]
            notification_id=uuid4()
        )
        assert result is None
        assert called == []

    async def test_dispatches_email_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the dispatch chain: get → parse_payload → render →
        # enqueue_email(to=user.email, subject, html).
        notif = MagicMock()
        notif.user.email = "alice@example.com"
        notifications = _patch_session(monkeypatch, notif=notif)

        notification_type = MagicMock()
        notification_type.render = MagicMock(return_value=("Subj", "<p>body</p>"))
        notifications.parse_payload = MagicMock(return_value=notification_type)

        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            M,
            "enqueue_email",
            lambda **kw: captured.update(kw),
        )

        await notifications_send.__wrapped__(  # type: ignore[attr-defined]
            notification_id=uuid4()
        )
        assert captured["to_email_addr"] == "alice@example.com"
        assert captured["subject"] == "Subj"
        assert captured["html_content"] == "<p>body</p>"
