"""Tests for ``rapidly/customers/customer_session/workers.py``.

Daily expired-customer-session cleanup cron. Two load-bearing
surfaces:

- The actor delegates to
  ``customer_session.delete_expired(session)`` — drift to a
  different action would silently leak stale sessions and
  bloat the table.
- The actor opens its own AsyncSession (the cron scheduler
  doesn't bring one). Drift to read from a missing context
  would crash the cron.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.customers.customer_session import workers as M
from rapidly.customers.customer_session.workers import (
    customer_session_delete_expired,
)


@pytest.mark.asyncio
class TestCustomerSessionDeleteExpired:
    async def test_delegates_to_delete_expired_action(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor opens a session and calls
        # ``customer_session.delete_expired(session)``. Drift would
        # silently no-op the cleanup and let the table grow
        # without bound.
        captured: dict[str, Any] = {}

        async def fake_delete_expired(session: Any) -> None:
            captured["session"] = session

        fake_actions = MagicMock()
        fake_actions.customer_session = MagicMock()
        fake_actions.customer_session.delete_expired = fake_delete_expired
        monkeypatch.setattr(M, "session_actions", fake_actions)

        session_obj = MagicMock(name="session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session_obj)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await customer_session_delete_expired.__wrapped__()  # type: ignore[attr-defined]
        assert captured["session"] is session_obj
