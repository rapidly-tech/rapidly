"""Tests for ``rapidly/messaging/email_update/workers.py``.

Daily expired-email-update cleanup cron. One load-bearing surface:
the actor delegates to
``email_update_actions.delete_expired_record(session)`` —
drift would leave stale verification rows in the table.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.messaging.email_update import workers as M
from rapidly.messaging.email_update.workers import (
    email_update_delete_expired_record,
)


@pytest.mark.asyncio
class TestEmailUpdateDeleteExpiredRecord:
    async def test_delegates_to_delete_expired_record_action(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor opens a session and calls
        # ``delete_expired_record(session)``. Drift would silently
        # leak verification rows.
        captured: dict[str, Any] = {}

        async def fake_delete_expired(session: Any) -> None:
            captured["session"] = session

        fake_actions = MagicMock()
        fake_actions.delete_expired_record = fake_delete_expired
        monkeypatch.setattr(M, "email_update_actions", fake_actions)

        session_obj = MagicMock(name="session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session_obj)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await email_update_delete_expired_record.__wrapped__()  # type: ignore[attr-defined]
        assert captured["session"] is session_obj
