"""Tests for ``rapidly/analytics/eventstream/workers.py``.

Eventstream-publish actor — pushes a serialised event to one or
more Redis pub/sub channels for SSE fan-out.

One load-bearing surface: the actor delegates to ``send_event``
with the RedisMiddleware-resolved client + the caller's event
string + channel list. Drift would silently drop fan-out.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from rapidly.analytics.eventstream import workers as M
from rapidly.analytics.eventstream.workers import eventstream_publish


@pytest.mark.asyncio
class TestEventstreamPublish:
    async def test_delegates_to_send_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the actor calls ``send_event(redis, event, channels)``
        # with the RedisMiddleware-resolved client. Drift would
        # silently drop the fan-out (clients miss events).
        captured: dict[str, object] = {}

        async def fake_send_event(
            redis: object, event: str, channels: list[str]
        ) -> None:
            captured["redis"] = redis
            captured["event"] = event
            captured["channels"] = channels

        monkeypatch.setattr(M, "send_event", fake_send_event)

        sentinel_redis = AsyncMock()
        monkeypatch.setattr(
            "rapidly.analytics.eventstream.workers.RedisMiddleware.get",
            staticmethod(lambda: sentinel_redis),
        )

        await eventstream_publish.__wrapped__(  # type: ignore[attr-defined]
            event="event-payload",
            channels=["chan-a", "chan-b"],
        )
        assert captured["redis"] is sentinel_redis
        assert captured["event"] == "event-payload"
        assert captured["channels"] == ["chan-a", "chan-b"]

    async def test_empty_channels_still_calls_send_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: empty channel list still invokes send_event
        # (which is responsible for handling the edge case).
        # Drift to short-circuit here would mask bugs in the
        # callers that build the channel list.
        called: list[bool] = []

        async def fake_send_event(
            redis: object, event: str, channels: list[str]
        ) -> None:
            called.append(True)

        monkeypatch.setattr(M, "send_event", fake_send_event)
        monkeypatch.setattr(
            "rapidly.analytics.eventstream.workers.RedisMiddleware.get",
            staticmethod(lambda: AsyncMock()),
        )

        await eventstream_publish.__wrapped__(  # type: ignore[attr-defined]
            event="x", channels=[]
        )
        assert called == [True]
