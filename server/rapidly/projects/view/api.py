"""HTTP routes for project views."""

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
from rapidly.projects.view import actions as view_actions
from rapidly.projects.view import ordering
from rapidly.projects.view import permissions as auth
from rapidly.projects.view import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/project-views", tags=["project-views", APITag.public])


@router.get(
    "/",
    summary="List Project Views",
    response_model=PaginatedList[schemas.ProjectView],
)
async def list(
    auth_subject: auth.ProjectViewsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectViewsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
    name: str | None = Query(
        None,
        description=(
            "Case-insensitive substring match on the view name. "
            "SQL ``%`` and ``_`` wildcards in the input are escaped."
        ),
        max_length=256,
    ),
    include_archived: bool = Query(False, description="Include archived views."),
) -> PaginatedList[schemas.ProjectView]:
    results, count = await view_actions.list_for_project(
        session,
        auth_subject,
        project_id=project_id,
        name=name,
        include_archived=include_archived,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectView.model_validate(v) for v in results], count, pagination
    )


@router.get(
    "/{id}",
    summary="Get Project View",
    response_model=schemas.ProjectView,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectViewID,
    auth_subject: auth.ProjectViewsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectView:
    view = await view_actions.get(session, auth_subject, id)
    if view is None:
        raise ResourceNotFound()
    return schemas.ProjectView.model_validate(view)


@router.post(
    "/",
    summary="Create Project View",
    response_model=schemas.ProjectView,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectViewCreate,
    auth_subject: auth.ProjectViewsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectView:
    view = await view_actions.create(session, auth_subject, body)
    return schemas.ProjectView.model_validate(view)


@router.patch(
    "/{id}",
    summary="Update Project View",
    response_model=schemas.ProjectView,
    responses={400: {}, 404: {}, 409: {}},
)
async def update(
    id: schemas.ProjectViewID,
    body: schemas.ProjectViewUpdate,
    auth_subject: auth.ProjectViewsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectView:
    view = await view_actions.get(session, auth_subject, id)
    if view is None:
        raise ResourceNotFound()
    updated = await view_actions.update(session, auth_subject, view, body)
    return schemas.ProjectView.model_validate(updated)


@router.post(
    "/{id}/archive",
    summary="Archive Project View",
    response_model=schemas.ProjectView,
    responses={404: {}},
)
async def archive(
    id: schemas.ProjectViewID,
    auth_subject: auth.ProjectViewsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectView:
    view = await view_actions.get(session, auth_subject, id)
    if view is None:
        raise ResourceNotFound()
    archived = await view_actions.archive(session, auth_subject, view)
    return schemas.ProjectView.model_validate(archived)


@router.post(
    "/{id}/unarchive",
    summary="Unarchive Project View",
    response_model=schemas.ProjectView,
    responses={404: {}},
)
async def unarchive(
    id: schemas.ProjectViewID,
    auth_subject: auth.ProjectViewsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectView:
    view = await view_actions.get(session, auth_subject, id)
    if view is None:
        raise ResourceNotFound()
    restored = await view_actions.unarchive(session, auth_subject, view)
    return schemas.ProjectView.model_validate(restored)


@router.delete(
    "/{id}",
    summary="Delete Project View",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.ProjectViewID,
    auth_subject: auth.ProjectViewsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    view = await view_actions.get(session, auth_subject, id)
    if view is None:
        raise ResourceNotFound()
    await view_actions.delete(session, auth_subject, view)
