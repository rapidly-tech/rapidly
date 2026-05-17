"""HTTP routes for project cycles."""

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
from rapidly.projects.cycle import actions as cycle_actions
from rapidly.projects.cycle import ordering
from rapidly.projects.cycle import permissions as auth
from rapidly.projects.cycle import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/project-cycles", tags=["project-cycles", APITag.public])

_WORK_ITEM_IDS_RESPONSE = list[UUID]


@router.get(
    "/",
    summary="List Project Cycles",
    response_model=PaginatedList[schemas.ProjectCycle],
)
async def list(
    auth_subject: auth.ProjectCyclesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectCyclesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
    include_archived: bool = Query(False, description="Include archived cycles."),
) -> PaginatedList[schemas.ProjectCycle]:
    results, count = await cycle_actions.list_for_project(
        session,
        auth_subject,
        project_id=project_id,
        include_archived=include_archived,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectCycle.model_validate(c) for c in results], count, pagination
    )


@router.get(
    "/{id}",
    summary="Get Project Cycle",
    response_model=schemas.ProjectCycle,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectCycleID,
    auth_subject: auth.ProjectCyclesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectCycle:
    cycle = await cycle_actions.get(session, auth_subject, id)
    if cycle is None:
        raise ResourceNotFound()
    return schemas.ProjectCycle.model_validate(cycle)


@router.post(
    "/",
    summary="Create Project Cycle",
    response_model=schemas.ProjectCycle,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectCycleCreate,
    auth_subject: auth.ProjectCyclesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectCycle:
    cycle = await cycle_actions.create(session, auth_subject, body)
    return schemas.ProjectCycle.model_validate(cycle)


@router.patch(
    "/{id}",
    summary="Update Project Cycle",
    response_model=schemas.ProjectCycle,
    responses={400: {}, 404: {}},
)
async def update(
    id: schemas.ProjectCycleID,
    body: schemas.ProjectCycleUpdate,
    auth_subject: auth.ProjectCyclesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectCycle:
    cycle = await cycle_actions.get(session, auth_subject, id)
    if cycle is None:
        raise ResourceNotFound()
    updated = await cycle_actions.update(session, auth_subject, cycle, body)
    return schemas.ProjectCycle.model_validate(updated)


@router.post(
    "/{id}/archive",
    summary="Archive Project Cycle",
    response_model=schemas.ProjectCycle,
    responses={404: {}},
)
async def archive(
    id: schemas.ProjectCycleID,
    auth_subject: auth.ProjectCyclesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectCycle:
    cycle = await cycle_actions.get(session, auth_subject, id)
    if cycle is None:
        raise ResourceNotFound()
    archived = await cycle_actions.archive(session, auth_subject, cycle)
    return schemas.ProjectCycle.model_validate(archived)


@router.post(
    "/{id}/unarchive",
    summary="Unarchive Project Cycle",
    response_model=schemas.ProjectCycle,
    responses={404: {}},
)
async def unarchive(
    id: schemas.ProjectCycleID,
    auth_subject: auth.ProjectCyclesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectCycle:
    cycle = await cycle_actions.get(session, auth_subject, id)
    if cycle is None:
        raise ResourceNotFound()
    restored = await cycle_actions.unarchive(session, auth_subject, cycle)
    return schemas.ProjectCycle.model_validate(restored)


@router.delete(
    "/{id}",
    summary="Delete Project Cycle",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.ProjectCycleID,
    auth_subject: auth.ProjectCyclesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    cycle = await cycle_actions.get(session, auth_subject, id)
    if cycle is None:
        raise ResourceNotFound()
    await cycle_actions.delete(session, auth_subject, cycle)


# ── Work-item membership ──


@router.get(
    "/{id}/work-items",
    summary="List Cycle Work Item IDs",
    response_model=_WORK_ITEM_IDS_RESPONSE,
    responses={404: {}},
)
async def list_work_items(
    id: schemas.ProjectCycleID,
    auth_subject: auth.ProjectCyclesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> _WORK_ITEM_IDS_RESPONSE:
    cycle = await cycle_actions.get(session, auth_subject, id)
    if cycle is None:
        raise ResourceNotFound()
    return await cycle_actions.list_work_item_ids(session, id)


@router.post(
    "/{id}/work-items",
    summary="Add Work Items to Cycle",
    status_code=204,
    responses={400: {}, 404: {}},
)
async def add_work_items(
    id: schemas.ProjectCycleID,
    body: schemas.ProjectCycleWorkItemAdd,
    auth_subject: auth.ProjectCyclesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    cycle = await cycle_actions.get(session, auth_subject, id)
    if cycle is None:
        raise ResourceNotFound()
    await cycle_actions.add_work_items(session, auth_subject, cycle, body.work_item_ids)


@router.delete(
    "/{id}/work-items",
    summary="Remove Work Items from Cycle",
    status_code=204,
    responses={400: {}, 404: {}},
)
async def remove_work_items(
    id: schemas.ProjectCycleID,
    body: schemas.ProjectCycleWorkItemAdd,
    auth_subject: auth.ProjectCyclesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    cycle = await cycle_actions.get(session, auth_subject, id)
    if cycle is None:
        raise ResourceNotFound()
    await cycle_actions.remove_work_items(
        session, auth_subject, cycle, body.work_item_ids
    )
