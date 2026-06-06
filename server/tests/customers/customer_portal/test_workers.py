"""Tests for ``rapidly/customers/customer_portal/workers.py``.

Daily expired-customer-session-code cleanup cron. Two
load-bearing pins:

- ``_CLEANUP_HOUR == 0`` / ``_CLEANUP_MINUTE == 0`` so this
  worker concentrates in the same midnight-UTC off-peak
  window as the 5 other identity / customer cleanup actors.
- The actor delegates to ``customer_session_service.delete_
  expired_codes(session)``. Drift would silently stop the
  cleanup and expired OTP rows would re-accumulate on
  ``customer_session_codes`` forever.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.customers.customer_portal import workers as M
from rapidly.customers.customer_portal.workers import (
    _CLEANUP_HOUR,
    _CLEANUP_MINUTE,
    customer_session_code_delete_expired,
)


class TestCleanupSchedule:
    def test_runs_at_midnight_utc(self) -> None:
        # Pin the schedule — same off-peak window as auth /
        # customer_session / login_code / member_session /
        # workspace_access_token.
        assert _CLEANUP_HOUR == 0
        assert _CLEANUP_MINUTE == 0


@pytest.mark.asyncio
class TestCustomerSessionCodeDeleteExpired:
    async def test_delegates_to_service_delete_expired_codes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor opens a session and calls
        # ``customer_session_service.delete_expired_codes
        # (session)``. The codes-specific name disambiguates
        # from the broader ``CustomerSessionService`` which
        # also has the unrelated ``request`` / ``authenticate``
        # methods.
        captured: dict[str, Any] = {}

        async def fake_delete_expired_codes(session: Any) -> None:
            captured["session"] = session

        fake_service = MagicMock()
        fake_service.delete_expired_codes = fake_delete_expired_codes
        monkeypatch.setattr(M, "customer_session_service", fake_service)

        session_obj = MagicMock(name="session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session_obj)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await customer_session_code_delete_expired.__wrapped__()  # type: ignore[attr-defined]
        assert captured["session"] is session_obj
