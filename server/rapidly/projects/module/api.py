"""HTTP routes for project modules."""

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
from rapidly.projects.module import actions as module_actions
from rapidly.projects.module import ordering
from rapidly.projects.module import permissions as auth
from rapidly.projects.module import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/project-modules", tags=["project-modules", APITag.public])

_WORK_ITEM_IDS_RESPONSE = list[UUID]


@router.get(
    "/",
    summary="List Project Modules",
    response_model=PaginatedList[schemas.ProjectModule],
)
async def list(
    auth_subject: auth.ProjectModulesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectModulesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
    include_archived: bool = Query(False, description="Include archived modules."),
) -> PaginatedList[schemas.ProjectModule]:
    results, count = await module_actions.list_for_project(
        session,
        auth_subject,
        project_id=project_id,
        include_archived=include_archived,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectModule.model_validate(m) for m in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Project Module",
    response_model=schemas.ProjectModule,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectModuleID,
    auth_subject: auth.ProjectModulesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectModule:
    module = await module_actions.get(session, auth_subject, id)
    if module is None:
        raise ResourceNotFound()
    return schemas.ProjectModule.model_validate(module)


@router.post(
    "/",
    summary="Create Project Module",
    response_model=schemas.ProjectModule,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectModuleCreate,
    auth_subject: auth.ProjectModulesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectModule:
    module = await module_actions.create(session, auth_subject, body)
    return schemas.ProjectModule.model_validate(module)


@router.patch(
    "/{id}",
    summary="Update Project Module",
    response_model=schemas.ProjectModule,
    responses={400: {}, 404: {}},
)
async def update(
    id: schemas.ProjectModuleID,
    body: schemas.ProjectModuleUpdate,
    auth_subject: auth.ProjectModulesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectModule:
    module = await module_actions.get(session, auth_subject, id)
    if module is None:
        raise ResourceNotFound()
    updated = await module_actions.update(session, auth_subject, module, body)
    return schemas.ProjectModule.model_validate(updated)


@router.post(
    "/{id}/archive",
    summary="Archive Project Module",
    response_model=schemas.ProjectModule,
    responses={404: {}},
)
async def archive(
    id: schemas.ProjectModuleID,
    auth_subject: auth.ProjectModulesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectModule:
    module = await module_actions.get(session, auth_subject, id)
    if module is None:
        raise ResourceNotFound()
    archived = await module_actions.archive(session, auth_subject, module)
    return schemas.ProjectModule.model_validate(archived)


@router.post(
    "/{id}/unarchive",
    summary="Unarchive Project Module",
    response_model=schemas.ProjectModule,
    responses={404: {}},
)
async def unarchive(
    id: schemas.ProjectModuleID,
    auth_subject: auth.ProjectModulesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectModule:
    module = await module_actions.get(session, auth_subject, id)
    if module is None:
        raise ResourceNotFound()
    restored = await module_actions.unarchive(session, auth_subject, module)
    return schemas.ProjectModule.model_validate(restored)


@router.delete(
    "/{id}",
    summary="Delete Project Module",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.ProjectModuleID,
    auth_subject: auth.ProjectModulesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    module = await module_actions.get(session, auth_subject, id)
    if module is None:
        raise ResourceNotFound()
    await module_actions.delete(session, auth_subject, module)


# ── Work-item membership ──


@router.get(
    "/{id}/work-items",
    summary="List Module Work Item IDs",
    response_model=_WORK_ITEM_IDS_RESPONSE,
    responses={404: {}},
)
async def list_work_items(
    id: schemas.ProjectModuleID,
    auth_subject: auth.ProjectModulesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> _WORK_ITEM_IDS_RESPONSE:
    module = await module_actions.get(session, auth_subject, id)
    if module is None:
        raise ResourceNotFound()
    return await module_actions.list_work_item_ids(session, id)


@router.post(
    "/{id}/work-items",
    summary="Add Work Items to Module",
    status_code=204,
    responses={400: {}, 404: {}},
)
async def add_work_items(
    id: schemas.ProjectModuleID,
    body: schemas.ProjectModuleWorkItemAdd,
    auth_subject: auth.ProjectModulesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    module = await module_actions.get(session, auth_subject, id)
    if module is None:
        raise ResourceNotFound()
    await module_actions.add_work_items(
        session, auth_subject, module, body.work_item_ids
    )


@router.delete(
    "/{id}/work-items",
    summary="Remove Work Items from Module",
    status_code=204,
    responses={400: {}, 404: {}},
)
async def remove_work_items(
    id: schemas.ProjectModuleID,
    body: schemas.ProjectModuleWorkItemAdd,
    auth_subject: auth.ProjectModulesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    module = await module_actions.get(session, auth_subject, id)
    if module is None:
        raise ResourceNotFound()
    await module_actions.remove_work_items(
        session, auth_subject, module, body.work_item_ids
    )
