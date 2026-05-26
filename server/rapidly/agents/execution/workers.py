"""Dramatiq actor that owns a Run from start to finish.

The actor is the only caller of ``engine.walk_run``. It owns the
session lifecycle, retry semantics, and the outermost exception
catch. ``walk_run`` itself is engine-pure: takes a session +
run_id, walks, returns.

Session-flush discipline (per the existing actor pattern):
``await session.flush()`` only; the actor framework persists at
task completion.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from rapidly.agents.execution.engine import walk_run
from rapidly.worker import AsyncSessionMaker, TaskPriority, actor

_log = structlog.get_logger(__name__)


@actor(actor_name="agents.execute_run", priority=TaskPriority.LOW, max_retries=2)
async def execute_run(run_id: UUID) -> None:
    """Dispatch a Run through the engine.

    Idempotent: ``walk_run`` checks the Run's status on entry and
    bails on terminal/cancelled. A re-dispatch (manual retry, dlq
    requeue) of a finished run is a no-op.
    """
    async with AsyncSessionMaker() as session:
        try:
            await walk_run(session, run_id)
        except Exception:
            _log.exception("agents.execute_run.unhandled", run_id=str(run_id))
            raise
