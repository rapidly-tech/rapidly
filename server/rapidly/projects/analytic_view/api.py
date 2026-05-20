"""HTTP routes for analytic views."""

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
from rapidly.projects.analytic_view import actions as av_actions
from rapidly.projects.analytic_view import ordering
from rapidly.projects.analytic_view import permissions as auth
from rapidly.projects.analytic_view import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/analytic-views", tags=["analytic-views", APITag.public])


@router.get(
    "/",
    summary="List Analytic Views",
    response_model=PaginatedList[schemas.AnalyticView],
)
async def list(
    auth_subject: auth.AnalyticViewsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.AnalyticViewsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    workspace_id: UUID | None = Query(None, description="Filter by workspace ID."),
    project_id: UUID | None = Query(
        None,
        description=(
            "Filter by project ID. Useful for project-scoped dashboards; "
            "workspace-wide dashboards have project_id=null."
        ),
    ),
) -> PaginatedList[schemas.AnalyticView]:
    results, count = await av_actions.list_views(
        session,
        auth_subject,
        workspace_id=workspace_id,
        project_id=project_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.AnalyticView.model_validate(v) for v in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Analytic View",
    response_model=schemas.AnalyticView,
    responses={404: {}},
)
async def get(
    id: schemas.AnalyticViewID,
    auth_subject: auth.AnalyticViewsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.AnalyticView:
    view = await av_actions.get(session, auth_subject, id)
    if view is None:
        raise ResourceNotFound()
    return schemas.AnalyticView.model_validate(view)


@router.post(
    "/",
    summary="Create Analytic View",
    response_model=schemas.AnalyticView,
    status_code=201,
    responses={400: {}, 404: {}},
)
async def create(
    body: schemas.AnalyticViewCreate,
    auth_subject: auth.AnalyticViewsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.AnalyticView:
    view = await av_actions.create(session, auth_subject, body)
    return schemas.AnalyticView.model_validate(view)


@router.patch(
    "/{id}",
    summary="Update Analytic View",
    response_model=schemas.AnalyticView,
    responses={400: {}, 404: {}},
)
async def update(
    id: schemas.AnalyticViewID,
    body: schemas.AnalyticViewUpdate,
    auth_subject: auth.AnalyticViewsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.AnalyticView:
    view = await av_actions.get(session, auth_subject, id)
    if view is None:
        raise ResourceNotFound()
    updated = await av_actions.update(session, auth_subject, view, body)
    return schemas.AnalyticView.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Analytic View",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.AnalyticViewID,
    auth_subject: auth.AnalyticViewsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    view = await av_actions.get(session, auth_subject, id)
    if view is None:
        raise ResourceNotFound()
    await av_actions.delete(session, auth_subject, view)
