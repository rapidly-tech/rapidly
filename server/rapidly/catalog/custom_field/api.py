"""Custom-field HTTP endpoints: CRUD operations.

Provides listing, creation, update, and deletion of custom-field
definitions within a workspace.
"""

from typing import Annotated

from fastapi import Depends, Path, Query
from pydantic import UUID4

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import ResourceNotFound
from rapidly.models import CustomField
from rapidly.models.custom_field import CustomFieldType
from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import ordering
from . import permissions as auth
from .actions import custom_field as custom_field_service
from .types import CustomField as CustomFieldSchema
from .types import CustomFieldAdapter, CustomFieldCreate, CustomFieldUpdate

router = APIRouter(prefix="/custom-fields", tags=["custom-fields", APITag.public])


CustomFieldID = Annotated[UUID4, Path(description="The custom field ID.")]
CustomFieldNotFound = {
    "description": "Custom field not found.",
    "model": ResourceNotFound.schema(),
}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=CustomFieldSchema,
    status_code=201,
    summary="Create Custom Field",
    responses={201: {"description": "Custom field created."}},
)
async def create(
    custom_field_create: CustomFieldCreate,
    auth_subject: auth.CustomFieldWrite,
    session: AsyncSession = Depends(get_db_session),
) -> CustomField:
    """Create a custom field."""
    return await custom_field_service.create(session, custom_field_create, auth_subject)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@router.get(
    "/{id}",
    summary="Get Custom Field",
    response_model=CustomFieldSchema,
    responses={404: CustomFieldNotFound},
)
async def get(
    id: CustomFieldID,
    auth_subject: auth.CustomFieldRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> CustomField:
    """Get a custom field by ID."""
    found = await custom_field_service.get_by_id(session, auth_subject, id)

    if found is None:
        raise ResourceNotFound()

    return found


@router.get(
    "/", summary="List Custom Fields", response_model=PaginatedList[CustomFieldSchema]
)
async def list_custom_fields_endpoint(
    auth_subject: auth.CustomFieldRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ListSorting,
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    query: str | None = Query(None, description="Filter by custom field name or slug."),
    type: MultipleQueryFilter[CustomFieldType] | None = Query(
        None, title="CustomFieldType Filter", description="Filter by custom field type."
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[CustomFieldSchema]:
    """List custom fields."""
    results, count = await custom_field_service.list_custom_fields(
        session,
        auth_subject,
        workspace_id=workspace_id,
        query=query,
        type=type,
        pagination=pagination,
        sorting=sorting,
    )

    return PaginatedList.from_paginated_results(
        [CustomFieldAdapter.validate_python(r) for r in results],
        count,
        pagination,
    )


# ---------------------------------------------------------------------------
# Update & Delete
# ---------------------------------------------------------------------------


@router.patch(
    "/{id}",
    response_model=CustomFieldSchema,
    summary="Update Custom Field",
    responses={
        200: {"description": "Custom field updated."},
        404: CustomFieldNotFound,
    },
)
async def update(
    id: CustomFieldID,
    custom_field_update: CustomFieldUpdate,
    auth_subject: auth.CustomFieldWrite,
    session: AsyncSession = Depends(get_db_session),
) -> CustomField:
    """Update a custom field."""
    found = await custom_field_service.get_by_id(session, auth_subject, id)

    if found is None:
        raise ResourceNotFound()

    return await custom_field_service.update(session, found, custom_field_update)


@router.delete(
    "/{id}",
    status_code=204,
    summary="Delete Custom Field",
    responses={
        204: {"description": "Custom field deleted."},
        404: CustomFieldNotFound,
    },
)
async def delete(
    id: CustomFieldID,
    auth_subject: auth.CustomFieldWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a custom field."""
    found = await custom_field_service.get_by_id(session, auth_subject, id)

    if found is None:
        raise ResourceNotFound()

    await custom_field_service.delete(session, found)
