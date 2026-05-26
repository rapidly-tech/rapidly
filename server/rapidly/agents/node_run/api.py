"""HTTP endpoints for node runs.

Nested under runs for URL clarity — node runs only make sense in
the context of their parent Run.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends

from rapidly.agents.node_run import actions
from rapidly.agents.node_run.permissions import NodeRunsRead
from rapidly.agents.node_run.types import NodeRunSchema
from rapidly.agents.run import actions as run_actions
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.openapi import APITag
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.routing import APIRouter

router = APIRouter(prefix="/v1/runs", tags=["node-runs", APITag.private])


@router.get(
    "/{run_id}/nodes",
    summary="List Node Runs",
    response_model=PaginatedList[NodeRunSchema],
)
async def list_node_runs(
    run_id: UUID,
    auth_subject: NodeRunsRead,
    pagination: PaginationParamsQuery,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[NodeRunSchema]:
    # 404 on the run first — cheaper than join + clearer error.
    await run_actions.get_or_raise(session, auth_subject, run_id)
    results, count = await actions.list_for_run(
        session, auth_subject, run_id=run_id, pagination=pagination
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get(
    "/{run_id}/nodes/{node_run_id}",
    summary="Get Node Run",
    response_model=NodeRunSchema,
)
async def get_node_run(
    run_id: UUID,
    node_run_id: UUID,
    auth_subject: NodeRunsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> NodeRunSchema:
    node_run = await actions.get_or_raise(session, auth_subject, node_run_id)
    if node_run.run_id != run_id:
        # Path mismatch — node run exists but doesn't belong to the
        # run in the URL. 404 not 403 so we don't leak existence.
        from rapidly.errors import ResourceNotFound

        raise ResourceNotFound("Node run not found.")
    return NodeRunSchema.model_validate(node_run)
