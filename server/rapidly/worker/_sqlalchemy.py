"""SQLAlchemy engine lifecycle for Dramatiq workers."""

import contextlib
import sys
from collections.abc import AsyncIterator

import dramatiq
import structlog
from dramatiq.asyncio import get_event_loop_thread

from rapidly.core.db.postgres import AsyncSessionMaker as AsyncSessionMakerType
from rapidly.core.db.postgres import create_async_sessionmaker
from rapidly.logfire import instrument_sqlalchemy
from rapidly.logging import Logger
from rapidly.postgres import AsyncEngine, AsyncSession, create_async_engine

_log: Logger = structlog.get_logger(__name__)

_DEFAULT_POOL_NAME: str = "worker"


def _resolve_pool_name() -> str:
    """Derive a pool name from the ``--queues`` CLI argument, if present."""
    try:
        idx = sys.argv.index("--queues")
        queues = sys.argv[idx + 1].split(",")
        return f"worker-{'-'.join(sorted(queues))}"
    except (ValueError, IndexError):
        return _DEFAULT_POOL_NAME


_engine: AsyncEngine | None = None
_sessionmaker: AsyncSessionMakerType | None = None


async def _dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _log.info("db.engine.disposed")
        _engine = None


class SQLAlchemyMiddleware(dramatiq.Middleware):
    """Create the async engine on worker boot, dispose it on shutdown."""

    @classmethod
    def get_async_session(cls) -> contextlib.AbstractAsyncContextManager[AsyncSession]:
        if _sessionmaker is None:
            raise RuntimeError("SQLAlchemy not initialised — worker not yet booted")
        return _sessionmaker()

    def before_worker_boot(
        self, broker: dramatiq.Broker, worker: dramatiq.Worker
    ) -> None:
        global _engine, _sessionmaker
        pool_name = _resolve_pool_name()
        _engine = create_async_engine("worker", pool_logging_name=pool_name)
        _sessionmaker = create_async_sessionmaker(_engine)
        instrument_sqlalchemy([_engine.sync_engine])
        _log.info("db.engine.created", pool=pool_name)

    def after_worker_shutdown(
        self, broker: dramatiq.Broker, worker: dramatiq.Worker
    ) -> None:
        loop_thread = get_event_loop_thread()
        assert loop_thread is not None
        loop_thread.run_coroutine(_dispose_engine())


@contextlib.asynccontextmanager
async def AsyncSessionMaker() -> AsyncIterator[AsyncSession]:
    """Scoped session with automatic commit/rollback for worker tasks."""
    async with SQLAlchemyMiddleware.get_async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
