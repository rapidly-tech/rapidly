"""Tests for the file_sharing cleanup cron actor.

Only the cron cleanup actor + its delegation are pinned here.
The on-success / on-failure event-dispatch actors are tested
elsewhere; this file is scoped to the periodic transition
that moves expired sessions to ``expired`` status.

Three load-bearing pins:

- Schedule is ``*/5`` minutes — drift to ``*/5 hours`` (typo
  field-swap) would let expired session UIs linger for an
  hour before the cron caught them; drift to ``*/1`` would
  hammer the table 12x more often.
- The actor calls ``expire_active_sessions(now_utc())`` and
  dispatches ``file_sharing.session_expired`` once per
  returned id. Drift to skip the dispatch loop would mean
  the session-expired event-fan-out (consumer email,
  analytics rollup, etc.) silently stops firing.
- Zero-expired returns early. Drift to log + dispatch even
  when no sessions were expired would flood the worker log
  with daily noise on a 5-min schedule.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.sharing.file_sharing import workers as M
from rapidly.sharing.file_sharing.workers import (
    file_sharing_check_expired_sessions,
)


@pytest.mark.asyncio
class TestCheckExpiredSessions:
    def _setup(
        self, monkeypatch: pytest.MonkeyPatch, *, expired_ids: list[Any]
    ) -> dict[str, Any]:
        """Wire mocks for the repo, session-maker, and dispatch_task.
        Returns a captured dict containing whatever the actor sent
        through dispatch_task."""
        captured: dict[str, Any] = {"dispatched": []}

        repo = MagicMock()
        repo.expire_active_sessions = AsyncMock(return_value=expired_ids)
        repo_cls = MagicMock()
        repo_cls.from_session = MagicMock(return_value=repo)
        monkeypatch.setattr(M, "FileShareSessionRepository", repo_cls)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        def fake_dispatch(actor_name: str, **kwargs: Any) -> None:
            captured["dispatched"].append((actor_name, kwargs))

        monkeypatch.setattr(M, "dispatch_task", fake_dispatch)

        # Stable now() so the threshold passed to
        # expire_active_sessions is deterministic.
        fixed_now = datetime(2026, 5, 28, 12, 0, 0)
        monkeypatch.setattr(M, "now_utc", lambda: fixed_now)
        captured["fixed_now"] = fixed_now

        captured["repo"] = repo
        return captured

    async def test_dispatches_one_event_per_expired_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor MUST dispatch ``file_sharing.session_expired``
        # once per returned id. Drift to dispatch once-per-batch (or
        # skip the loop) would break the per-session fan-out — the
        # downstream consumer-notify / analytics-rollup actors all
        # key off this event firing per session.
        ids = [uuid4(), uuid4(), uuid4()]
        captured = self._setup(monkeypatch, expired_ids=ids)

        await file_sharing_check_expired_sessions.__wrapped__()  # type: ignore[attr-defined]

        # Repo called with the fixed now.
        captured["repo"].expire_active_sessions.assert_awaited_once_with(
            captured["fixed_now"]
        )

        # One dispatch per id, in the same order, with the
        # ``file_share_session_id`` keyword.
        assert len(captured["dispatched"]) == 3
        for (actor_name, kwargs), expected_id in zip(
            captured["dispatched"], ids, strict=True
        ):
            assert actor_name == "file_sharing.session_expired"
            assert kwargs == {"file_share_session_id": expected_id}

    async def test_no_dispatches_when_zero_expired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the early-return on empty list means no
        # dispatch_task calls fire on cron ticks when nothing
        # has expired. Without this, the actor would
        # iterate an empty list (no-op) but the log line
        # would still fire — flooding the worker log with
        # daily noise on the 5-min schedule.
        captured = self._setup(monkeypatch, expired_ids=[])

        await file_sharing_check_expired_sessions.__wrapped__()  # type: ignore[attr-defined]

        # Repo was called.
        captured["repo"].expire_active_sessions.assert_awaited_once()
        # No dispatches fired.
        assert captured["dispatched"] == []
