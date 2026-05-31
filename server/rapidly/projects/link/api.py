"""HTTP routes for work-item relations."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.link import actions as link_actions
from rapidly.projects.link import ordering
from rapidly.projects.link import permissions as auth
from rapidly.projects.link import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/work-item-relations", tags=["work-item-relations", APITag.public]
)


@router.get(
    "/",
    summary="List Work Item Relations",
    response_model=PaginatedList[schemas.WorkItemRelation],
)
async def list(
    auth_subject: auth.WorkItemRelationsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemRelationsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    work_item_id: UUID = Query(
        ..., description="Required filter; returns relations both directions."
    ),
) -> PaginatedList[schemas.WorkItemRelation]:
    results, count = await link_actions.list_for_work_item(
        session,
        auth_subject,
        work_item_id=work_item_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemRelation.model_validate(r) for r in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Work Item Relation",
    response_model=schemas.WorkItemRelation,
    responses={404: {}},
)
async def get(
    id: schemas.WorkItemRelationID,
    auth_subject: auth.WorkItemRelationsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.WorkItemRelation:
    relation = await link_actions.get(session, auth_subject, id)
    if relation is None:
        raise ResourceNotFound()
    return schemas.WorkItemRelation.model_validate(relation)


@router.post(
    "/",
    summary="Create Work Item Relation",
    response_model=schemas.WorkItemRelation,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.WorkItemRelationCreate,
    auth_subject: auth.WorkItemRelationsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemRelation:
    relation = await link_actions.create(session, auth_subject, body)
    return schemas.WorkItemRelation.model_validate(relation)


@router.delete(
    "/{id}",
    summary="Delete Work Item Relation",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.WorkItemRelationID,
    auth_subject: auth.WorkItemRelationsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    relation = await link_actions.get(session, auth_subject, id)
    if relation is None:
        raise ResourceNotFound()
    await link_actions.delete(session, auth_subject, relation)
