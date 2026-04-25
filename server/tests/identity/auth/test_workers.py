"""Tests for ``rapidly/identity/auth/workers.py``.

Daily auth-data cleanup cron. Two load-bearing surfaces:

- The actor delegates to ``auth_service.delete_expired(session)``
  to remove expired sessions, tokens, and authorization codes.
  Drift would silently leak expired auth records (security:
  attackers replaying session cookies past their TTL would still
  match a row).
- ``_CLEANUP_HOUR == 0`` and ``_CLEANUP_MINUTE == 0`` — pin the
  midnight UTC cron schedule. Drift to a busier slot would
  compete with billing reconciliation jobs.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.identity.auth import workers as M
from rapidly.identity.auth.workers import (
    _CLEANUP_HOUR,
    _CLEANUP_MINUTE,
    auth_delete_expired,
)


class TestCleanupSchedule:
    def test_runs_at_midnight_utc(self) -> None:
        # Pin the schedule. A drift to e.g. business-hours would
        # compete with billing reconciliation and analytics rollups.
        assert _CLEANUP_HOUR == 0
        assert _CLEANUP_MINUTE == 0


@pytest.mark.asyncio
class TestAuthDeleteExpired:
    async def test_delegates_to_auth_service_delete_expired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor opens a session and calls
        # ``auth_service.delete_expired(session)``. Drift would
        # silently leak expired sessions, tokens, and OAuth codes
        # (security exposure: replay window extends indefinitely).
        captured: dict[str, Any] = {}

        async def fake_delete_expired(session: Any) -> None:
            captured["session"] = session

        fake_actions = MagicMock()
        fake_actions.delete_expired = fake_delete_expired
        monkeypatch.setattr(M, "auth_service", fake_actions)

        session_obj = MagicMock(name="session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session_obj)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await auth_delete_expired.__wrapped__()  # type: ignore[attr-defined]
        assert captured["session"] is session_obj
