"""Dramatiq middleware that manages a shared HTTPX AsyncClient for workers."""

import dramatiq
import httpx
import structlog
from dramatiq.asyncio import get_event_loop_thread

from rapidly.logging import Logger

_log: Logger = structlog.get_logger(__name__)

_client: httpx.AsyncClient | None = None


async def _teardown_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _log.info("HTTPX client closed")
        _client = None


class HTTPXMiddleware(dramatiq.Middleware):
    """Lifecycle middleware for a shared HTTPX AsyncClient."""

    @classmethod
    def get(cls) -> httpx.AsyncClient:
        if _client is None:
            raise RuntimeError("HTTPX client has not been initialised")
        return _client

    def before_worker_boot(
        self, broker: dramatiq.Broker, worker: dramatiq.Worker
    ) -> None:
        global _client
        _client = httpx.AsyncClient()
        _log.info("HTTPX client created")

    def after_worker_shutdown(
        self, broker: dramatiq.Broker, worker: dramatiq.Worker
    ) -> None:
        loop_thread = get_event_loop_thread()
        assert loop_thread is not None
        loop_thread.run_coroutine(_teardown_client())
