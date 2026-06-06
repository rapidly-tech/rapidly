"""Tests for ``rapidly/identity/login_code/workers.py``.

Daily expired-login-code cleanup cron. Two load-bearing pins:

- ``_CLEANUP_HOUR == 0`` / ``_CLEANUP_MINUTE == 0`` so this
  worker concentrates in the same midnight-UTC off-peak
  window as the 5 other identity-cleanup actors (auth,
  customer_session, member_session, customer_session_code,
  workspace_access_token).
- The actor delegates to ``login_code_service.delete_expired
  (session)``. Drift would silently stop the cleanup and
  expired codes would re-accumulate on ``login_codes`` forever
  (the success path deletes on redemption, but never-redeemed
  codes — the common case — would linger without this).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.identity.login_code import workers as M
from rapidly.identity.login_code.workers import (
    _CLEANUP_HOUR,
    _CLEANUP_MINUTE,
    login_code_delete_expired,
)


class TestCleanupSchedule:
    def test_runs_at_midnight_utc(self) -> None:
        # Pin the schedule. Drift to a business-hours slot
        # would compete with billing reconciliation + the 5
        # sibling identity-cleanup actors that share this
        # off-peak window by design.
        assert _CLEANUP_HOUR == 0
        assert _CLEANUP_MINUTE == 0


@pytest.mark.asyncio
class TestLoginCodeDeleteExpired:
    async def test_delegates_to_service_delete_expired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor opens a session and calls
        # ``login_code_service.delete_expired(session)``. Drift
        # would silently stop the cleanup and expired codes
        # would re-accumulate on the table.
        captured: dict[str, Any] = {}

        async def fake_delete_expired(session: Any) -> None:
            captured["session"] = session

        fake_service = MagicMock()
        fake_service.delete_expired = fake_delete_expired
        monkeypatch.setattr(M, "login_code_service", fake_service)

        session_obj = MagicMock(name="session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session_obj)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await login_code_delete_expired.__wrapped__()  # type: ignore[attr-defined]
        assert captured["session"] is session_obj
