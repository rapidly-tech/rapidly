"""Tests for ``rapidly/analytics/event/workers.py``.

Event-ingestion fan-out actor. Three load-bearing surfaces:

- ``_ACTOR_NAME = "event.ingested"`` — JobQueueManager.flush
  dispatches under this literal name; drift would silently lose
  every event-ingested fan-out (webhook delivery, analytics
  aggregation).
- ``_MAX_RETRIES = 5`` — events fan out to external webhooks, so
  transient delivery failures need a meaningful retry budget.
  Drift down (e.g., 1) would lose events on a single transient
  failure; drift up would amplify webhook-receiver failures.
- ``_MIN_BACKOFF_MS = 30_000`` — 30s base backoff. Drift down would
  hammer flaky webhook receivers; drift up would delay legitimate
  retries past customer-visible deadlines.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rapidly.analytics.event import workers as M
from rapidly.analytics.event.workers import (
    _ACTOR_NAME,
    _MAX_RETRIES,
    _MIN_BACKOFF_MS,
    event_ingested,
)


class TestActorConstants:
    def test_actor_name_pinned(self) -> None:
        # Pin the literal that JobQueueManager.flush dispatches
        # under (see rapidly/worker/_enqueue.py — every events
        # batch becomes one event.ingested task).
        assert _ACTOR_NAME == "event.ingested"

    def test_max_retries_pinned(self) -> None:
        # Pin: 5 retries — events fan out to external webhooks
        # so transient delivery failures need a meaningful budget.
        # Drift down loses events; drift up amplifies receiver
        # failures.
        assert _MAX_RETRIES == 5

    def test_min_backoff_30_seconds(self) -> None:
        # Pin: 30s base backoff. Drift down would hammer flaky
        # webhook receivers; drift up would delay legitimate
        # retries.
        assert _MIN_BACKOFF_MS == 30_000


@pytest.mark.asyncio
class TestEventIngested:
    async def test_delegates_to_actions_ingested(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor's job is to open a session and call
        # ``event_actions.ingested(session, event_ids)``. Drift
        # would silently no-op the ingestion fan-out.
        captured: dict[str, object] = {}

        async def fake_ingested(session: object, ids: object) -> None:
            captured["session"] = session
            captured["ids"] = ids

        fake_actions = MagicMock()
        fake_actions.ingested = fake_ingested
        monkeypatch.setattr(M, "event_actions", fake_actions)

        # AsyncSessionMaker yields a fake session as a context
        # manager.
        session_obj = MagicMock(name="session")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session_obj)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        ids = [uuid4(), uuid4(), uuid4()]
        await event_ingested.__wrapped__(event_ids=ids)  # type: ignore[attr-defined]

        assert captured["session"] is session_obj
        assert captured["ids"] == ids

    async def test_handles_empty_event_ids(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: an empty event list still opens the session
        # and calls ``ingested`` (the action layer decides what
        # to do with empty input). Drift to short-circuit on
        # empty would let a bug in the dispatcher silently skip
        # legitimate-but-empty fanouts.
        called: list[bool] = []

        async def fake_ingested(session: object, ids: object) -> None:
            called.append(True)

        fake_actions = MagicMock()
        fake_actions.ingested = fake_ingested
        monkeypatch.setattr(M, "event_actions", fake_actions)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=MagicMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(M, "AsyncSessionMaker", lambda: cm)

        await event_ingested.__wrapped__(event_ids=[])  # type: ignore[attr-defined]
        assert called == [True]
