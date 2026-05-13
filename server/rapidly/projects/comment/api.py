"""HTTP routes for work-item comments."""

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
from rapidly.projects.comment import actions as comment_actions
from rapidly.projects.comment import ordering
from rapidly.projects.comment import permissions as auth
from rapidly.projects.comment import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/work-item-comments", tags=["work-item-comments", APITag.public]
)


@router.get(
    "/",
    summary="List Work Item Comments",
    response_model=PaginatedList[schemas.WorkItemComment],
)
async def list(
    auth_subject: auth.WorkItemCommentsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemCommentsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    work_item_id: UUID = Query(..., description="Required filter by work-item ID."),
) -> PaginatedList[schemas.WorkItemComment]:
    results, count = await comment_actions.list_for_work_item(
        session,
        auth_subject,
        work_item_id=work_item_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemComment.model_validate(c) for c in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Work Item Comment",
    response_model=schemas.WorkItemComment,
    responses={404: {}},
)
async def get(
    id: schemas.WorkItemCommentID,
    auth_subject: auth.WorkItemCommentsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.WorkItemComment:
    comment = await comment_actions.get(session, auth_subject, id)
    if comment is None:
        raise ResourceNotFound()
    return schemas.WorkItemComment.model_validate(comment)


@router.post(
    "/",
    summary="Create Work Item Comment",
    response_model=schemas.WorkItemComment,
    status_code=201,
    responses={403: {}, 404: {}},
)
async def create(
    body: schemas.WorkItemCommentCreate,
    auth_subject: auth.WorkItemCommentsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemComment:
    comment = await comment_actions.create(session, auth_subject, body)
    return schemas.WorkItemComment.model_validate(comment)


@router.patch(
    "/{id}",
    summary="Update Work Item Comment",
    response_model=schemas.WorkItemComment,
    responses={403: {}, 404: {}},
)
async def update(
    id: schemas.WorkItemCommentID,
    body: schemas.WorkItemCommentUpdate,
    auth_subject: auth.WorkItemCommentsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemComment:
    comment = await comment_actions.get(session, auth_subject, id)
    if comment is None:
        raise ResourceNotFound()
    updated = await comment_actions.update(session, auth_subject, comment, body)
    return schemas.WorkItemComment.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Work Item Comment",
    status_code=204,
    responses={403: {}, 404: {}},
)
async def delete(
    id: schemas.WorkItemCommentID,
    auth_subject: auth.WorkItemCommentsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    comment = await comment_actions.get(session, auth_subject, id)
    if comment is None:
        raise ResourceNotFound()
    await comment_actions.delete(session, auth_subject, comment)
