"""HTTP routes for work-item types."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.work_item_type import actions as type_actions
from rapidly.projects.work_item_type import ordering
from rapidly.projects.work_item_type import permissions as auth
from rapidly.projects.work_item_type import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/work-item-types", tags=["work-item-types", APITag.public])


@router.get(
    "/",
    summary="List Work Item Types",
    response_model=PaginatedList[schemas.WorkItemType],
)
async def list(
    auth_subject: auth.WorkItemTypesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemTypesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
) -> PaginatedList[schemas.WorkItemType]:
    results, count = await type_actions.list_for_project(
        session,
        auth_subject,
        project_id=project_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemType.model_validate(t) for t in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Work Item Type",
    response_model=schemas.WorkItemType,
    responses={404: {}},
)
async def get(
    id: schemas.WorkItemTypeID,
    auth_subject: auth.WorkItemTypesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.WorkItemType:
    work_item_type = await type_actions.get(session, auth_subject, id)
    if work_item_type is None:
        raise ResourceNotFound()
    return schemas.WorkItemType.model_validate(work_item_type)


@router.post(
    "/",
    summary="Create Work Item Type",
    response_model=schemas.WorkItemType,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.WorkItemTypeCreate,
    auth_subject: auth.WorkItemTypesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemType:
    work_item_type = await type_actions.create(session, auth_subject, body)
    return schemas.WorkItemType.model_validate(work_item_type)


@router.patch(
    "/{id}",
    summary="Update Work Item Type",
    response_model=schemas.WorkItemType,
    responses={400: {}, 404: {}, 409: {}},
)
async def update(
    id: schemas.WorkItemTypeID,
    body: schemas.WorkItemTypeUpdate,
    auth_subject: auth.WorkItemTypesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemType:
    work_item_type = await type_actions.get(session, auth_subject, id)
    if work_item_type is None:
        raise ResourceNotFound()
    updated = await type_actions.update(session, auth_subject, work_item_type, body)
    return schemas.WorkItemType.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Work Item Type",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.WorkItemTypeID,
    auth_subject: auth.WorkItemTypesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    work_item_type = await type_actions.get(session, auth_subject, id)
    if work_item_type is None:
        raise ResourceNotFound()
    await type_actions.delete(session, auth_subject, work_item_type)
