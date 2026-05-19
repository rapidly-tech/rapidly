"""HTTP routes for work-item external links."""

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
from rapidly.projects.external_link import actions as link_actions
from rapidly.projects.external_link import ordering
from rapidly.projects.external_link import permissions as auth
from rapidly.projects.external_link import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/work-item-links", tags=["work-item-links", APITag.public])


@router.get(
    "/",
    summary="List Work Item External Links",
    response_model=PaginatedList[schemas.WorkItemLink],
)
async def list(
    auth_subject: auth.WorkItemLinksRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemLinksSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    work_item_id: UUID = Query(
        ..., description="Required filter; returns links for this work item."
    ),
) -> PaginatedList[schemas.WorkItemLink]:
    results, count = await link_actions.list_for_work_item(
        session,
        auth_subject,
        work_item_id=work_item_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemLink.model_validate(r) for r in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Work Item External Link",
    response_model=schemas.WorkItemLink,
    responses={404: {}},
)
async def get(
    id: schemas.WorkItemLinkID,
    auth_subject: auth.WorkItemLinksRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.WorkItemLink:
    link = await link_actions.get(session, auth_subject, id)
    if link is None:
        raise ResourceNotFound()
    return schemas.WorkItemLink.model_validate(link)


@router.post(
    "/",
    summary="Create Work Item External Link",
    response_model=schemas.WorkItemLink,
    status_code=201,
    responses={400: {}, 404: {}},
)
async def create(
    body: schemas.WorkItemLinkCreate,
    auth_subject: auth.WorkItemLinksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemLink:
    link = await link_actions.create(session, auth_subject, body)
    return schemas.WorkItemLink.model_validate(link)


@router.patch(
    "/{id}",
    summary="Update Work Item External Link",
    response_model=schemas.WorkItemLink,
    responses={400: {}, 404: {}},
)
async def update(
    id: schemas.WorkItemLinkID,
    body: schemas.WorkItemLinkUpdate,
    auth_subject: auth.WorkItemLinksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemLink:
    link = await link_actions.get(session, auth_subject, id)
    if link is None:
        raise ResourceNotFound()
    updated = await link_actions.update(session, auth_subject, link, body)
    return schemas.WorkItemLink.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Work Item External Link",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.WorkItemLinkID,
    auth_subject: auth.WorkItemLinksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    link = await link_actions.get(session, auth_subject, id)
    if link is None:
        raise ResourceNotFound()
    await link_actions.delete(session, auth_subject, link)
