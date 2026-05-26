"""NodeRun read surface for the API.

The engine (M4.2) is the only writer; it reaches into the
repository's inherited ``create`` + ``update`` directly. Public
actions here are list + get only.
"""

from collections.abc import Sequence
from uuid import UUID

from rapidly.agents.node_run.queries import NodeRunRepository
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.errors import ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.models import NodeRun
from rapidly.postgres import AsyncReadSession, AsyncSession


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> NodeRun | None:
    repo = NodeRunRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(NodeRun.id == id)
    return await repo.get_one_or_none(stmt)


async def get_or_raise(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> NodeRun:
    node_run = await get(session, auth_subject, id)
    if node_run is None:
        raise ResourceNotFound("Node run not found.")
    return node_run


async def list_for_run(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    run_id: UUID,
    pagination: PaginationParams,
) -> tuple[Sequence[NodeRun], int]:
    repo = NodeRunRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject).where(
        NodeRun.run_id == run_id
    )
    return await paginate(session, statement, pagination=pagination)
