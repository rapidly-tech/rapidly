"""Tests for ``rapidly/middlewares/workers.py::JobDispatchMiddleware``.

The middleware opens a ``JobQueueManager`` context around each HTTP /
WebSocket request so that any jobs enqueued during handling are
flushed to the Dramatiq broker atomically on completion. Lifespan
scopes must pass through unchanged — the manager depends on
``scope["state"]["redis"]`` which lifespan scopes don't carry.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import cast

import pytest
from starlette.types import Message, Receive, Scope, Send

from rapidly.middlewares.workers import JobDispatchMiddleware


async def _noop_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _noop_send(_: Message) -> None:
    pass


class _RecordingManager:
    """Stub JobQueueManager that records enter/exit + the args it
    was opened with."""

    entered: list[tuple[object, object]] = []
    exited: list[bool] = []

    @classmethod
    @asynccontextmanager
    async def open(cls, broker: object, redis: object):  # type: ignore[no-untyped-def]
        cls.entered.append((broker, redis))
        try:
            yield cls
        finally:
            cls.exited.append(True)

    @classmethod
    def reset(cls) -> None:
        cls.entered = []
        cls.exited = []


@pytest.fixture(autouse=True)
def _patch_manager_and_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    _RecordingManager.reset()
    monkeypatch.setattr(
        "rapidly.middlewares.workers.JobQueueManager",
        _RecordingManager,
    )
    # dramatiq.get_broker() returns a sentinel we can recognise.
    monkeypatch.setattr(
        "rapidly.middlewares.workers.dramatiq.get_broker",
        lambda: "fake-broker",
    )


@pytest.mark.asyncio
class TestJobDispatchMiddleware:
    async def test_opens_and_closes_JobQueueManager_around_downstream(
        self,
    ) -> None:
        order: list[str] = []

        async def _app(scope: Scope, receive: Receive, send: Send) -> None:
            order.append("downstream")

        mw = JobDispatchMiddleware(_app)
        await mw(
            cast(
                Scope,
                {
                    "type": "http",
                    "state": {"redis": "fake-redis"},
                },
            ),
            _noop_receive,
            _noop_send,
        )
        # Manager opened, downstream ran, manager closed — in that order.
        assert _RecordingManager.entered == [("fake-broker", "fake-redis")]
        assert order == ["downstream"]
        assert _RecordingManager.exited == [True]

    async def test_closes_manager_even_when_downstream_raises(self) -> None:
        async def _exploding(scope: Scope, receive: Receive, send: Send) -> None:
            raise RuntimeError("boom")

        mw = JobDispatchMiddleware(_exploding)
        with pytest.raises(RuntimeError):
            await mw(
                cast(
                    Scope,
                    {"type": "http", "state": {"redis": "fake-redis"}},
                ),
                _noop_receive,
                _noop_send,
            )
        # ``finally`` in the async context manager must still fire so
        # pending jobs don't leak across failed requests.
        assert _RecordingManager.exited == [True]

    async def test_handles_websocket_scopes(self) -> None:
        async def _app(scope: Scope, receive: Receive, send: Send) -> None:
            pass

        mw = JobDispatchMiddleware(_app)
        await mw(
            cast(
                Scope,
                {"type": "websocket", "state": {"redis": "fake-redis"}},
            ),
            _noop_receive,
            _noop_send,
        )
        assert _RecordingManager.entered == [("fake-broker", "fake-redis")]

    async def test_passes_through_lifespan_scopes_without_opening_manager(
        self,
    ) -> None:
        # Lifespan scopes don't carry ``state["redis"]`` — opening the
        # manager would ``KeyError``. The scope-type guard must short-
        # circuit.
        ran: list[bool] = []

        async def _lifespan(scope: Scope, receive: Receive, send: Send) -> None:
            ran.append(True)

        mw = JobDispatchMiddleware(_lifespan)
        await mw(
            cast(Scope, {"type": "lifespan"}),
            _noop_receive,
            _noop_send,
        )
        # Downstream ran, but manager was NOT opened.
        assert ran == [True]
        assert _RecordingManager.entered == []
        assert _RecordingManager.exited == []
