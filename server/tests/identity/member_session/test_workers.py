"""Tests for ``rapidly/identity/member_session/workers.py``.

Daily expired-member-session cleanup cron. Two load-bearing
pins:

- ``_CLEANUP_HOUR == 0`` / ``_CLEANUP_MINUTE == 0`` so this
  worker concentrates in the same midnight-UTC off-peak
  window as the 5 other identity-cleanup actors.
- The actor delegates to ``member_session_service.delete_
  expired(session)``. Drift would silently stop the cleanup
  — the action + query layers were already present (this
  worker was the missing piece) so a regression would be
  particularly easy to miss.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.identity.member_session import workers as M
from rapidly.identity.member_session.workers import (
    _CLEANUP_HOUR,
    _CLEANUP_MINUTE,
    member_session_delete_expired,
)


class TestCleanupSchedule:
    def test_runs_at_midnight_utc(self) -> None:
        # Pin the schedule — same off-peak window as auth /
        # customer_session / login_code / etc.
        assert _CLEANUP_HOUR == 0
        assert _CLEANUP_MINUTE == 0


@pytest.mark.asyncio
class TestMemberSessionDeleteExpired:
    async def test_delegates_to_service_delete_expired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor opens a session and calls
        # ``member_session_service.delete_expired(session)``.
        # The action + query layers existed for ages but no
        # worker invoked them; a regression that drops the
        # action call would silently re-introduce the
        # pre-PR-#856 gap.
        captured: dict[str, Any] = {}

        async def fake_delete_expired(session: Any) -> None:
            captured["session"] = session

        fake_service = MagicMock()
        fake_service.delete_expired = fake_delete_expired
        monkeypatch.setattr(M, "member_session_service", fake_service)

        session_obj = MagicMock(name="session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session_obj)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await member_session_delete_expired.__wrapped__()  # type: ignore[attr-defined]
        assert captured["session"] is session_obj
