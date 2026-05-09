"""Tests for ``rapidly/worker/_httpx.py``.

Dramatiq lifecycle middleware for a shared ``httpx.AsyncClient``.
A SINGLE client per worker process means connections pool across
actors — pinning the before-boot/after-shutdown cycle keeps that
invariant intact.

Pins:
- ``HTTPXMiddleware.get()`` raises ``RuntimeError`` when the client
  hasn't been initialised yet (actor accidentally firing before
  boot would silently get None — crash loudly instead)
- ``before_worker_boot`` builds a fresh ``httpx.AsyncClient`` and
  stashes it in module state
- ``_teardown_client`` closes the client and resets module state to
  None so a re-boot rebuilds cleanly
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from rapidly.worker import _httpx as M
from rapidly.worker._httpx import HTTPXMiddleware, _teardown_client


@pytest.fixture(autouse=True)
def reset_client() -> object:
    """Reset module-level _client around every test — keeps tests
    isolated from each other and from real worker state."""
    original = M._client
    M._client = None
    try:
        yield
    finally:
        M._client = original


class TestGetWithoutInit:
    def test_raises_runtime_error_when_client_is_none(self) -> None:
        # Load-bearing defensive pin: an actor firing before
        # ``before_worker_boot`` has run must crash loudly rather
        # than silently hand back None — the latter would surface
        # as an ``AttributeError`` deep inside httpx call sites.
        M._client = None
        with pytest.raises(RuntimeError, match="not been initialised"):
            HTTPXMiddleware.get()


class TestGetAfterInit:
    def test_returns_the_module_level_client(self) -> None:
        sentinel = MagicMock(name="httpx-client")
        M._client = sentinel
        assert HTTPXMiddleware.get() is sentinel


class TestBeforeWorkerBoot:
    def test_creates_a_real_async_client(self) -> None:
        mw = HTTPXMiddleware()
        assert M._client is None
        mw.before_worker_boot(MagicMock(), MagicMock())
        assert isinstance(M._client, httpx.AsyncClient)

    def test_replaces_existing_client_on_reboot(self) -> None:
        # A re-boot must build a fresh client — reusing a closed
        # one would leak sockets; holding a stale reference would
        # miss reconnects across worker restarts.
        first = MagicMock(name="old-client")
        M._client = first
        mw = HTTPXMiddleware()
        mw.before_worker_boot(MagicMock(), MagicMock())
        assert M._client is not first


@pytest.mark.asyncio
class TestTeardownClient:
    async def test_aclose_called_and_client_reset(self) -> None:
        fake = MagicMock(name="httpx-client")
        fake.aclose = AsyncMock()
        M._client = fake
        await _teardown_client()
        fake.aclose.assert_awaited_once()
        assert M._client is None

    async def test_noop_when_client_is_none(self) -> None:
        # Shutdown-before-boot must not raise. The helper uses an
        # ``if _client is not None`` guard; pin it so a refactor
        # that dropped the guard would crash the worker shutdown
        # path loudly.
        M._client = None
        await _teardown_client()
        assert M._client is None
