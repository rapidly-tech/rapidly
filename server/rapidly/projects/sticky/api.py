"""HTTP routes for stickies."""

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
from rapidly.projects.sticky import actions as sticky_actions
from rapidly.projects.sticky import ordering
from rapidly.projects.sticky import permissions as auth
from rapidly.projects.sticky import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/stickies", tags=["stickies", APITag.public])


@router.get(
    "/",
    summary="List My Stickies",
    response_model=PaginatedList[schemas.Sticky],
)
async def list(
    auth_subject: auth.StickiesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.StickiesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    workspace_id: UUID | None = Query(
        None, description="Optional filter — return stickies in this workspace only."
    ),
) -> PaginatedList[schemas.Sticky]:
    results, count = await sticky_actions.list_mine(
        session,
        auth_subject,
        workspace_id=workspace_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.Sticky.model_validate(s) for s in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Sticky",
    response_model=schemas.Sticky,
    responses={404: {}},
)
async def get(
    id: schemas.StickyID,
    auth_subject: auth.StickiesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.Sticky:
    sticky = await sticky_actions.get(session, auth_subject, id)
    if sticky is None:
        raise ResourceNotFound()
    return schemas.Sticky.model_validate(sticky)


@router.post(
    "/",
    summary="Create Sticky",
    response_model=schemas.Sticky,
    status_code=201,
    responses={400: {}},
)
async def create(
    body: schemas.StickyCreate,
    auth_subject: auth.StickiesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.Sticky:
    sticky = await sticky_actions.create(session, auth_subject, body)
    return schemas.Sticky.model_validate(sticky)


@router.patch(
    "/{id}",
    summary="Update Sticky",
    response_model=schemas.Sticky,
    responses={400: {}, 404: {}},
)
async def update(
    id: schemas.StickyID,
    body: schemas.StickyUpdate,
    auth_subject: auth.StickiesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.Sticky:
    sticky = await sticky_actions.get(session, auth_subject, id)
    if sticky is None:
        raise ResourceNotFound()
    updated = await sticky_actions.update(session, auth_subject, sticky, body)
    return schemas.Sticky.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Sticky",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.StickyID,
    auth_subject: auth.StickiesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    sticky = await sticky_actions.get(session, auth_subject, id)
    if sticky is None:
        raise ResourceNotFound()
    await sticky_actions.delete(session, auth_subject, sticky)
