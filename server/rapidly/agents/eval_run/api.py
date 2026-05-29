"""HTTP endpoints for eval runs.

``/api/v1/agents/eval-runs/*``

Read-mostly: trigger creates a pending row + dispatches an actor;
list + get + cases return the runner's progress + results.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Query, status

from rapidly.agents.eval_run import actions
from rapidly.agents.eval_run.permissions import EvalRunsRead, EvalRunsWrite
from rapidly.agents.eval_run.types import (
    EvalRunCaseSchema,
    EvalRunSchema,
    EvalRunTrigger,
)
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.models.eval_run import AssertionStrategy, EvalRunStatus
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

router = APIRouter(prefix="/v1/agents/eval-runs", tags=["eval-runs", APITag.private])


@router.get(
    "/",
    summary="List Eval Runs",
    response_model=PaginatedList[EvalRunSchema],
)
async def list_eval_runs(
    auth_subject: EvalRunsRead,
    pagination: PaginationParamsQuery,
    workspace_id: UUID | None = Query(
        None,
        description=(
            "Narrow to a single workspace. Unknown IDs return an empty "
            "set rather than 403 so we don't leak membership."
        ),
    ),
    dataset_id: UUID | None = Query(None),
    workflow_version_id: UUID | None = Query(None),
    status_filter: EvalRunStatus | None = Query(None, alias="status"),
    assertion_strategy: AssertionStrategy | None = Query(
        None,
        description=(
            "Filter by assertion strategy: ``exact_match``, "
            "``json_schema``, or ``llm_judge``. Omit for all."
        ),
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[EvalRunSchema]:
    results, count = await actions.list_eval_runs(
        session,
        auth_subject,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        workflow_version_id=workflow_version_id,
        status=status_filter,
        assertion_strategy=assertion_strategy,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get("/{id}", summary="Get Eval Run", response_model=EvalRunSchema)
async def get_eval_run(
    id: UUID,
    auth_subject: EvalRunsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> EvalRunSchema:
    eval_run = await actions.get_or_raise(session, auth_subject, id)
    return EvalRunSchema.model_validate(eval_run)


@router.get(
    "/{id}/cases",
    summary="List Eval Run Cases",
    response_model=list[EvalRunCaseSchema],
)
async def list_eval_run_cases(
    id: UUID,
    auth_subject: EvalRunsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> list[EvalRunCaseSchema]:
    eval_run = await actions.get_or_raise(session, auth_subject, id)
    rows = await actions.list_cases(session, eval_run)
    return [EvalRunCaseSchema.model_validate(c) for c in rows]


@router.post(
    "/",
    summary="Trigger Eval Run",
    response_model=EvalRunSchema,
    status_code=status.HTTP_202_ACCEPTED,
    description=(
        "Create an eval run + dispatch the runner actor. The "
        "response is 202 Accepted — the eval is created in "
        "``pending`` state and the actor flips it to "
        "``running`` on pickup. Poll the GET /{id} endpoint "
        "to watch the pass/fail counters tick up."
    ),
)
async def trigger_eval_run(
    body: EvalRunTrigger,
    auth_subject: EvalRunsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunSchema:
    eval_run = await actions.trigger(session, auth_subject, body)
    return EvalRunSchema.model_validate(eval_run)


@router.post(
    "/{id}/cancel",
    summary="Cancel Eval Run",
    response_model=EvalRunSchema,
    description=(
        "Flip a pending/running eval run to ``cancelled``. The runner "
        "re-reads status before scoring each case, so case results already "
        "computed are kept and remaining cases are skipped. Returns 403 "
        "if the run is already in a terminal status."
    ),
)
async def cancel_eval_run(
    id: UUID,
    auth_subject: EvalRunsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> EvalRunSchema:
    eval_run = await actions.get_or_raise(session, auth_subject, id)
    cancelled = await actions.cancel(session, auth_subject, eval_run)
    return EvalRunSchema.model_validate(cancelled)
