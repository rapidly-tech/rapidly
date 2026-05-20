"""HTTP routes for the project intake queue."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import ResourceNotFound
from rapidly.models import IntakeSource, IntakeStatus
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.intake import actions as intake_actions
from rapidly.projects.intake import ordering
from rapidly.projects.intake import permissions as auth
from rapidly.projects.intake import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/intake-work-items", tags=["intake-work-items", APITag.public]
)


@router.get(
    "/",
    summary="List Intake Work Items",
    response_model=PaginatedList[schemas.IntakeWorkItem],
)
async def list(
    auth_subject: auth.IntakeRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.IntakeWorkItemsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: UUID = Query(
        ..., description="Required filter; returns the intake queue for this project."
    ),
    status: IntakeStatus | None = Query(None, description="Optional triage filter."),
    source: IntakeSource | None = Query(None, description="Optional source filter."),
) -> PaginatedList[schemas.IntakeWorkItem]:
    results, count = await intake_actions.list_for_project(
        session,
        auth_subject,
        project_id=project_id,
        status=status,
        source=source,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.IntakeWorkItem.model_validate(r) for r in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Intake Work Item",
    response_model=schemas.IntakeWorkItem,
    responses={404: {}},
)
async def get(
    id: schemas.IntakeWorkItemID,
    auth_subject: auth.IntakeRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.IntakeWorkItem:
    intake = await intake_actions.get(session, auth_subject, id)
    if intake is None:
        raise ResourceNotFound()
    return schemas.IntakeWorkItem.model_validate(intake)


@router.post(
    "/",
    summary="Add Work Item to Intake Queue",
    response_model=schemas.IntakeWorkItem,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.IntakeWorkItemCreate,
    auth_subject: auth.IntakeWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.IntakeWorkItem:
    intake = await intake_actions.create(session, auth_subject, body)
    return schemas.IntakeWorkItem.model_validate(intake)


@router.patch(
    "/{id}",
    summary="Triage Intake Work Item",
    response_model=schemas.IntakeWorkItem,
    responses={400: {}, 404: {}},
)
async def update(
    id: schemas.IntakeWorkItemID,
    body: schemas.IntakeWorkItemUpdate,
    auth_subject: auth.IntakeWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.IntakeWorkItem:
    intake = await intake_actions.get(session, auth_subject, id)
    if intake is None:
        raise ResourceNotFound()
    updated = await intake_actions.transition(session, auth_subject, intake, body)
    return schemas.IntakeWorkItem.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Remove from Intake Queue",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.IntakeWorkItemID,
    auth_subject: auth.IntakeWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    intake = await intake_actions.get(session, auth_subject, id)
    if intake is None:
        raise ResourceNotFound()
    await intake_actions.delete(session, auth_subject, intake)
