"""HTTP routes for work-item subscribers."""

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
from rapidly.projects.subscriber import actions as subscriber_actions
from rapidly.projects.subscriber import ordering
from rapidly.projects.subscriber import permissions as auth
from rapidly.projects.subscriber import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/work-item-subscribers",
    tags=["work-item-subscribers", APITag.public],
)


@router.get(
    "/",
    summary="List Work Item Subscribers",
    response_model=PaginatedList[schemas.WorkItemSubscriber],
)
async def list(
    auth_subject: auth.WorkItemSubscribersRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemSubscribersSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    work_item_id: UUID = Query(
        ..., description="Required filter; returns subscribers for this work item."
    ),
) -> PaginatedList[schemas.WorkItemSubscriber]:
    results, count = await subscriber_actions.list_for_work_item(
        session,
        auth_subject,
        work_item_id=work_item_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemSubscriber.model_validate(s) for s in results],
        count,
        pagination,
    )


@router.get(
    "/me",
    summary="List My Subscriptions",
    response_model=PaginatedList[schemas.WorkItemSubscriber],
)
async def list_mine(
    auth_subject: auth.WorkItemSubscribersWrite,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemSubscribersSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[schemas.WorkItemSubscriber]:
    """Return the caller's own subscriptions across all work items."""
    results, count = await subscriber_actions.list_subscribed_for_user(
        session,
        auth_subject,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemSubscriber.model_validate(s) for s in results],
        count,
        pagination,
    )


@router.post(
    "/",
    summary="Subscribe to Work Item",
    response_model=schemas.WorkItemSubscriber,
    status_code=201,
    responses={404: {}, 409: {}},
)
async def subscribe(
    body: schemas.WorkItemSubscribeCreate,
    auth_subject: auth.WorkItemSubscribersWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemSubscriber:
    subscription = await subscriber_actions.subscribe(
        session, auth_subject, work_item_id=body.work_item_id
    )
    return schemas.WorkItemSubscriber.model_validate(subscription)


@router.delete(
    "/{id}",
    summary="Unsubscribe from Work Item",
    status_code=204,
    responses={404: {}},
)
async def unsubscribe(
    id: schemas.WorkItemSubscriberID,
    auth_subject: auth.WorkItemSubscribersWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    subscription = await subscriber_actions.get(session, auth_subject, id)
    if subscription is None:
        raise ResourceNotFound()
    await subscriber_actions.unsubscribe(session, auth_subject, subscription)
