"""HTTP endpoints for LLM usage read + rollup.

``/api/v1/agents/llm-usage/*``

Read-only — writes happen inside the LLM handler as part of run
execution. Two surfaces:

    GET /v1/agents/llm-usage           — raw paginated list
    GET /v1/agents/llm-usage/rollup    — grouped aggregate
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import Depends, Query

from rapidly.agents.llm_usage import actions
from rapidly.agents.llm_usage.permissions import LlmUsageRead
from rapidly.agents.llm_usage.types import (
    CredentialBudgetResponse,
    LlmUsageSchema,
    UsageRollupResponse,
)
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.openapi import APITag
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/v1/agents/llm-usage",
    tags=["llm-usage", APITag.private],
)


@router.get(
    "/",
    summary="List LLM Usage Records",
    response_model=PaginatedList[LlmUsageSchema],
)
async def list_usage(
    auth_subject: LlmUsageRead,
    pagination: PaginationParamsQuery,
    credential_id: UUID | None = Query(None),
    provider: str | None = Query(None),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[LlmUsageSchema]:
    results, count = await actions.list_usage(
        session,
        auth_subject,
        credential_id=credential_id,
        provider=provider,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get(
    "/rollup",
    summary="Grouped Usage Rollup",
    response_model=UsageRollupResponse,
    description=(
        "Return a grouped rollup of LLM usage. Groups by "
        "``(workspace_id, credential_id, provider, model)`` and "
        "sums tokens + call_count within the requested window. "
        "Defaults to the last 24 hours; windows over 90 days are "
        "clamped — use an offline export for longer ranges."
    ),
)
async def rollup(
    auth_subject: LlmUsageRead,
    window_start: datetime | None = Query(None),
    window_end: datetime | None = Query(None),
    credential_id: UUID | None = Query(None),
    provider: str | None = Query(None),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> UsageRollupResponse:
    return await actions.rollup(
        session,
        auth_subject,
        window_start=window_start,
        window_end=window_end,
        credential_id=credential_id,
        provider=provider,
    )


@router.get(
    "/budgets",
    summary="Credential Budgets",
    response_model=CredentialBudgetResponse,
    description=(
        "Return each visible credential's month-to-date token "
        "consumption and (if set) its monthly budget + percent "
        "used. The MTD anchor is the first day of the current "
        "month in UTC. Operators on other timezones can compute "
        "their own anchor and use the /rollup endpoint instead."
    ),
)
async def budgets(
    auth_subject: LlmUsageRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> CredentialBudgetResponse:
    return await actions.budgets(session, auth_subject)
