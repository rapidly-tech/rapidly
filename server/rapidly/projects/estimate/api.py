"""Project estimate HTTP routes: scale CRUD + nested point management."""

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
from rapidly.projects.estimate import actions as estimate_actions
from rapidly.projects.estimate import ordering
from rapidly.projects.estimate import permissions as auth
from rapidly.projects.estimate import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/project-estimates", tags=["project-estimates", APITag.public]
)

# Materialised before ``async def list`` shadows the ``list`` builtin below.
_POINTS_LIST_RESPONSE = list[schemas.ProjectEstimatePoint]


# ── Estimates ──


@router.get(
    "/",
    summary="List Project Estimates",
    response_model=PaginatedList[schemas.ProjectEstimate],
)
async def list(
    auth_subject: auth.ProjectEstimatesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectEstimatesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
    name: str | None = Query(
        None,
        description=(
            "Case-insensitive substring match on the estimate display name. "
            "SQL ``%`` and ``_`` wildcards in the input are escaped."
        ),
        max_length=256,
    ),
) -> PaginatedList[schemas.ProjectEstimate]:
    results, count = await estimate_actions.list(
        session,
        auth_subject,
        project_id=project_id,
        name=name,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectEstimate.model_validate(e) for e in results], count, pagination
    )


@router.get(
    "/{id}",
    summary="Get Project Estimate",
    response_model=schemas.ProjectEstimate,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectEstimateID,
    auth_subject: auth.ProjectEstimatesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectEstimate:
    estimate = await estimate_actions.get(session, auth_subject, id)
    if estimate is None:
        raise ResourceNotFound()
    return schemas.ProjectEstimate.model_validate(estimate)


@router.post(
    "/",
    summary="Create Project Estimate",
    response_model=schemas.ProjectEstimate,
    status_code=201,
    responses={404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectEstimateCreate,
    auth_subject: auth.ProjectEstimatesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectEstimate:
    estimate = await estimate_actions.create(session, auth_subject, body)
    return schemas.ProjectEstimate.model_validate(estimate)


@router.patch(
    "/{id}",
    summary="Update Project Estimate",
    response_model=schemas.ProjectEstimate,
    responses={404: {}},
)
async def update(
    id: schemas.ProjectEstimateID,
    body: schemas.ProjectEstimateUpdate,
    auth_subject: auth.ProjectEstimatesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectEstimate:
    estimate = await estimate_actions.get(session, auth_subject, id)
    if estimate is None:
        raise ResourceNotFound()
    updated = await estimate_actions.update(session, auth_subject, estimate, body)
    return schemas.ProjectEstimate.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Project Estimate",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.ProjectEstimateID,
    auth_subject: auth.ProjectEstimatesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    estimate = await estimate_actions.get(session, auth_subject, id)
    if estimate is None:
        raise ResourceNotFound()
    await estimate_actions.delete(session, auth_subject, estimate)


# ── Points (nested under estimates) ──


@router.get(
    "/{id}/points",
    summary="List Project Estimate Points",
    response_model=_POINTS_LIST_RESPONSE,
    responses={404: {}},
)
async def list_points(
    id: schemas.ProjectEstimateID,
    auth_subject: auth.ProjectEstimatesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> _POINTS_LIST_RESPONSE:
    estimate = await estimate_actions.get(session, auth_subject, id)
    if estimate is None:
        raise ResourceNotFound()
    results = await estimate_actions.list_points(session, auth_subject, estimate_id=id)
    return [schemas.ProjectEstimatePoint.model_validate(p) for p in results]


@router.post(
    "/points",
    summary="Create Project Estimate Point",
    response_model=schemas.ProjectEstimatePoint,
    status_code=201,
    responses={404: {}, 409: {}},
)
async def create_point(
    body: schemas.ProjectEstimatePointCreate,
    auth_subject: auth.ProjectEstimatesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectEstimatePoint:
    point = await estimate_actions.create_point(session, auth_subject, body)
    return schemas.ProjectEstimatePoint.model_validate(point)


@router.patch(
    "/points/{id}",
    summary="Update Project Estimate Point",
    response_model=schemas.ProjectEstimatePoint,
    responses={404: {}},
)
async def update_point(
    id: schemas.ProjectEstimatePointID,
    body: schemas.ProjectEstimatePointUpdate,
    auth_subject: auth.ProjectEstimatesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectEstimatePoint:
    point = await estimate_actions.get_point(session, auth_subject, id)
    if point is None:
        raise ResourceNotFound()
    updated = await estimate_actions.update_point(session, auth_subject, point, body)
    return schemas.ProjectEstimatePoint.model_validate(updated)


@router.delete(
    "/points/{id}",
    summary="Delete Project Estimate Point",
    status_code=204,
    responses={404: {}},
)
async def delete_point(
    id: schemas.ProjectEstimatePointID,
    auth_subject: auth.ProjectEstimatesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    point = await estimate_actions.get_point(session, auth_subject, id)
    if point is None:
        raise ResourceNotFound()
    await estimate_actions.delete_point(session, auth_subject, point)
