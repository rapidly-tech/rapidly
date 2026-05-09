"""Workspace access token HTTP routes: CRUD and scope management.

Provides endpoints for creating, listing, updating, and revoking
workspace-scoped access tokens (OATs) used for programmatic
API access.
"""

from fastapi import Depends, Query
from pydantic import UUID4

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import ResourceNotFound
from rapidly.models import WorkspaceAccessToken
from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import actions as workspace_access_token_service
from . import ordering
from .permissions import WorkspaceAccessTokensRead, WorkspaceAccessTokensWrite
from .types import (
    WorkspaceAccessToken as WorkspaceAccessTokenSchema,
)
from .types import (
    WorkspaceAccessTokenCreate,
    WorkspaceAccessTokenCreateResponse,
    WorkspaceAccessTokenUpdate,
)

router = APIRouter(
    prefix="/workspace-access-tokens",
    tags=["workspace_access_tokens", APITag.public, APITag.mcp],
)


# ── CRUD ──


@router.get("/", response_model=PaginatedList[WorkspaceAccessTokenSchema])
async def list(
    auth_subject: WorkspaceAccessTokensRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[WorkspaceAccessTokenSchema]:
    """List workspace access tokens."""
    results, count = await workspace_access_token_service.list(
        session,
        auth_subject,
        workspace_id=workspace_id,
        pagination=pagination,
        sorting=sorting,
    )

    return PaginatedList.from_paginated_results(
        [WorkspaceAccessTokenSchema.model_validate(result) for result in results],
        count,
        pagination,
    )


@router.post("/", response_model=WorkspaceAccessTokenCreateResponse, status_code=201)
async def create(
    workspace_access_token_create: WorkspaceAccessTokenCreate,
    auth_subject: WorkspaceAccessTokensWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceAccessTokenCreateResponse:
    workspace_access_token, token = await workspace_access_token_service.create(
        session, auth_subject, workspace_access_token_create
    )
    return WorkspaceAccessTokenCreateResponse.model_validate(
        {
            "workspace_access_token": workspace_access_token,
            "token": token,
        }
    )


@router.patch("/{id}", response_model=WorkspaceAccessTokenSchema)
async def update(
    id: UUID4,
    workspace_access_token_update: WorkspaceAccessTokenUpdate,
    auth_subject: WorkspaceAccessTokensWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceAccessToken:
    workspace_access_token = await workspace_access_token_service.get(
        session, auth_subject, id
    )
    if workspace_access_token is None:
        raise ResourceNotFound()

    return await workspace_access_token_service.update(
        session, workspace_access_token, workspace_access_token_update
    )


@router.delete("/{id}", status_code=204)
async def delete(
    id: UUID4,
    auth_subject: WorkspaceAccessTokensWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    workspace_access_token = await workspace_access_token_service.get(
        session, auth_subject, id
    )
    if workspace_access_token is None:
        raise ResourceNotFound()

    await workspace_access_token_service.delete(session, workspace_access_token)
