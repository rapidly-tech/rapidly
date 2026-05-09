"""Server-Sent Events (SSE) streaming for real-time dashboard updates.

Uses Redis pub/sub to fan out live event notifications to connected
clients, with per-workspace channel isolation.  Includes a workaround
to detect Uvicorn shutdown so SSE connections can be closed gracefully.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from fastapi import Depends, Request
from redis.exceptions import ConnectionError
from sse_starlette.sse import EventSourceResponse
from uvicorn import Server

from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.dependencies import WebUserRead
from rapidly.platform.workspace import actions as workspace_service
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from .actions import Receivers

router = APIRouter(prefix="/stream", tags=["stream"], include_in_schema=False)

_log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Uvicorn shutdown detection
# ---------------------------------------------------------------------------


def _uvicorn_should_exit() -> bool:
    """Public alias used by tests and the subscribe loop."""
    return _server_is_shutting_down()


def _server_is_shutting_down() -> bool:
    """Inspect running asyncio tasks for a Uvicorn ``Server`` instance.

    This is necessary because ``sse_starlette``'s exit-signal monkey-patch
    does not work when Uvicorn is started from the CLI, which would
    otherwise prevent graceful shutdown while an SSE connection is open.
    """
    try:
        for running_task in asyncio.all_tasks():
            coro = running_task.get_coro()
            if coro is None:
                continue
            frame = coro.cr_frame  # type: ignore
            if frame is None:
                continue
            local_vars = frame.f_locals
            if self := local_vars.get("self"):
                if isinstance(self, Server):
                    return self.should_exit
    except RuntimeError:
        pass
    return False


# ---------------------------------------------------------------------------
# Redis pub/sub subscription generator
# ---------------------------------------------------------------------------


async def subscribe(
    redis: Redis,
    channels: list[str],
    request: Request,
    on_iteration: Any = None,
) -> AsyncGenerator[Any, Any]:
    async with redis.pubsub() as pubsub:
        await pubsub.subscribe(*channels)

        while not _uvicorn_should_exit():
            if await request.is_disconnected():
                await pubsub.close()
                break

            if on_iteration is not None:
                await on_iteration()

            try:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=10.0,
                )

                if msg is not None:
                    _log.info("redis.pubsub", message=msg["data"])
                    yield msg["data"]
            except asyncio.CancelledError as exc:
                await pubsub.close()
                raise exc
            except ConnectionError as exc:
                await pubsub.close()
                raise exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/user")
async def user_stream(
    request: Request,
    auth_subject: WebUserRead,
    session: AsyncReadSession = Depends(get_db_read_session),
    redis: Redis = Depends(get_redis),
) -> EventSourceResponse:
    # Close the session to release the DB connection back to the pool
    # before entering the long-lived SSE stream.
    await session.close()
    receivers = Receivers(user_id=auth_subject.subject.id)
    return EventSourceResponse(subscribe(redis, receivers.get_channels(), request))


@router.get("/workspaces/{id}")
async def org_stream(
    id: WorkspaceID,
    request: Request,
    auth_subject: WebUserRead,
    redis: Redis = Depends(get_redis),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> EventSourceResponse:
    workspace = await workspace_service.get(session, auth_subject, id)
    if workspace is None:
        raise ResourceNotFound()

    # Close the session to release the DB connection back to the pool
    # before entering the long-lived SSE stream.
    await session.close()

    receivers = Receivers(user_id=auth_subject.subject.id, workspace_id=workspace.id)
    return EventSourceResponse(subscribe(redis, receivers.get_channels(), request))
