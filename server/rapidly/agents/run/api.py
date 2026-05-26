"""HTTP endpoints for runs.

List + get live at the top-level ``/api/v1/runs/`` for the "all my
runs across workflows" view. Trigger lives under the workflow URL
because it's an action against a specific workflow. Cancel sits
on the run id directly.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Query, status

from rapidly.agents.run import actions
from rapidly.agents.run.permissions import RunsRead, RunsTrigger
from rapidly.agents.run.types import RunSchema, RunTriggerRequest
from rapidly.agents.workflow import actions as workflow_actions
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.models import RunStatus
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

router = APIRouter(prefix="/v1/runs", tags=["runs", APITag.private])


@router.get(
    "/",
    summary="List Runs",
    response_model=PaginatedList[RunSchema],
)
async def list_runs(
    auth_subject: RunsRead,
    pagination: PaginationParamsQuery,
    workflow_version_id: UUID | None = Query(None),
    status_filter: RunStatus | None = Query(None, alias="status"),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[RunSchema]:
    results, count = await actions.list_runs(
        session,
        auth_subject,
        workflow_version_id=workflow_version_id,
        status=status_filter,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get(
    "/{id}",
    summary="Get Run",
    response_model=RunSchema,
)
async def get_run(
    id: UUID,
    auth_subject: RunsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> RunSchema:
    run = await actions.get_or_raise(session, auth_subject, id)
    return RunSchema.model_validate(run)


@router.post(
    "/{id}/cancel",
    summary="Cancel Run",
    response_model=RunSchema,
)
async def cancel_run(
    id: UUID,
    auth_subject: RunsTrigger,
    session: AsyncSession = Depends(get_db_session),
) -> RunSchema:
    run = await actions.get_or_raise(session, auth_subject, id)
    cancelled = await actions.cancel(session, auth_subject, run)
    return RunSchema.model_validate(cancelled)


# The trigger route is nested under the workflow id. It lives in
# its own router so the URL space stays readable; FastAPI lets us
# mount multiple routers under the same /api/v1 prefix.
trigger_router = APIRouter(prefix="/v1/workflows", tags=["runs", APITag.private])


@trigger_router.post(
    "/{workflow_id}/runs",
    summary="Trigger Workflow Run",
    response_model=RunSchema,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_run(
    workflow_id: UUID,
    body: RunTriggerRequest,
    auth_subject: RunsTrigger,
    session: AsyncSession = Depends(get_db_session),
) -> RunSchema:
    # Pre-flight gate the workflow read; the actual engine arrives
    # in M4.2.
    await workflow_actions.get_or_raise(session, auth_subject, workflow_id)
    # 501 until the engine ships. Body is parsed so request-schema
    # validation still happens at the boundary.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Workflow execution not implemented yet — engine ships in "
            "M4.2. The request shape + auth gate are wired so the M5 "
            "UI can build against this contract."
        ),
    )
