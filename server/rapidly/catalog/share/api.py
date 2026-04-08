"""Share HTTP routes: CRUD, price management, and media attachments.

Provides endpoints for creating, listing, updating, and archiving
products, managing associated prices (fixed and custom), and
attaching media files and custom fields.
"""

from typing import Annotated

from fastapi import Depends, Query

from rapidly.core.metadata import MetadataQuery, get_metadata_query_openapi_schema
from rapidly.core.ordering import Sorting, SortingGetter
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import NotPermitted, ResourceNotFound
from rapidly.models import Share
from rapidly.models.share import ShareVisibility
from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import actions as share_service
from . import permissions as auth
from .ordering import ShareSortProperty
from .types import Share as ShareSchema
from .types import ShareCreate, ShareID, ShareUpdate

router = APIRouter(
    prefix="/shares",
    tags=["shares", APITag.public, APITag.mcp],
)

ProductNotFound = {
    "description": "Share not found.",
    "model": ResourceNotFound.schema(),
}


ListSorting = Annotated[
    list[Sorting[ShareSortProperty]],
    Depends(SortingGetter(ShareSortProperty, ["-created_at"])),
]


# ── CRUD ──


@router.get(
    "/",
    name="list",
    summary="List Shares",
    response_model=PaginatedList[ShareSchema],
    openapi_extra={"parameters": [get_metadata_query_openapi_schema()]},
)
async def list_shares(
    pagination: PaginationParamsQuery,
    sorting: ListSorting,
    auth_subject: auth.CreatorSharesRead,
    metadata: MetadataQuery,
    id: MultipleQueryFilter[ShareID] | None = Query(
        None, title="ShareID Filter", description="Filter by share ID."
    ),
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    query: str | None = Query(None, description="Filter by share name."),
    is_archived: bool | None = Query(None, description="Filter on archived products."),
    visibility: list[ShareVisibility] | None = Query(
        default=None,
        description="Filter by visibility.",
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[ShareSchema]:
    """List products."""
    results, count = await share_service.list_shares(
        session,
        auth_subject,
        id=id,
        workspace_id=workspace_id,
        query=query,
        is_archived=is_archived,
        visibility=visibility,
        metadata=metadata,
        pagination=pagination,
        sorting=sorting,
    )

    return PaginatedList.from_paginated_results(
        [ShareSchema.model_validate(result) for result in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Share",
    response_model=ShareSchema,
    responses={404: ProductNotFound},
)
async def get(
    id: ShareID,
    auth_subject: auth.CreatorSharesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> Share:
    """Get a share by ID."""
    share = await share_service.get(session, auth_subject, id)

    if share is None:
        raise ResourceNotFound()

    return share


@router.post(
    "/",
    response_model=ShareSchema,
    status_code=201,
    summary="Create Share",
    responses={201: {"description": "Share created."}},
)
async def create(
    share_create: ShareCreate,
    auth_subject: auth.CreatorSharesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> Share:
    """Create a share."""
    return await share_service.create(session, share_create, auth_subject)


@router.patch(
    "/{id}",
    response_model=ShareSchema,
    summary="Update Share",
    responses={
        200: {"description": "Share updated."},
        403: {
            "description": "You don't have the permission to update this share.",
            "model": NotPermitted.schema(),
        },
        404: ProductNotFound,
    },
)
async def update(
    id: ShareID,
    share_update: ShareUpdate,
    auth_subject: auth.CreatorSharesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> Share:
    """Update a share."""
    share = await share_service.get(session, auth_subject, id)

    if share is None:
        raise ResourceNotFound()

    return await share_service.update(session, share, share_update, auth_subject)
