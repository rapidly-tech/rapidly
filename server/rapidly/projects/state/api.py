"""Project state HTTP routes: CRUD."""

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
from rapidly.projects.state import actions as state_actions
from rapidly.projects.state import ordering
from rapidly.projects.state import permissions as auth
from rapidly.projects.state import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/project-states", tags=["project-states", APITag.public])


@router.get(
    "/",
    summary="List Project States",
    response_model=PaginatedList[schemas.ProjectState],
)
async def list(
    auth_subject: auth.ProjectStatesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectStatesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
) -> PaginatedList[schemas.ProjectState]:
    results, count = await state_actions.list(
        session,
        auth_subject,
        project_id=project_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectState.model_validate(s) for s in results], count, pagination
    )


@router.get(
    "/{id}",
    summary="Get Project State",
    response_model=schemas.ProjectState,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectStateID,
    auth_subject: auth.ProjectStatesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectState:
    state = await state_actions.get(session, auth_subject, id)
    if state is None:
        raise ResourceNotFound()
    return schemas.ProjectState.model_validate(state)


@router.post(
    "/",
    summary="Create Project State",
    response_model=schemas.ProjectState,
    status_code=201,
    responses={404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectStateCreate,
    auth_subject: auth.ProjectStatesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectState:
    state = await state_actions.create(session, auth_subject, body)
    return schemas.ProjectState.model_validate(state)


@router.patch(
    "/{id}",
    summary="Update Project State",
    response_model=schemas.ProjectState,
    responses={404: {}},
)
async def update(
    id: schemas.ProjectStateID,
    body: schemas.ProjectStateUpdate,
    auth_subject: auth.ProjectStatesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectState:
    state = await state_actions.get(session, auth_subject, id)
    if state is None:
        raise ResourceNotFound()
    updated = await state_actions.update(session, auth_subject, state, body)
    return schemas.ProjectState.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Project State",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.ProjectStateID,
    auth_subject: auth.ProjectStatesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    state = await state_actions.get(session, auth_subject, id)
    if state is None:
        raise ResourceNotFound()
    await state_actions.delete(session, auth_subject, state)
