"""HTTP routes for project pages."""

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
from rapidly.projects.page import actions as page_actions
from rapidly.projects.page import ordering
from rapidly.projects.page import permissions as auth
from rapidly.projects.page import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/project-pages", tags=["project-pages", APITag.public])


@router.get(
    "/",
    summary="List Project Pages",
    response_model=PaginatedList[schemas.ProjectPage],
)
async def list(
    auth_subject: auth.ProjectPagesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectPagesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
    parent_id: UUID | None = Query(
        None, description="Filter pages whose parent is this ID."
    ),
    include_archived: bool = Query(False, description="Include archived pages."),
    name: str | None = Query(
        None,
        description=(
            "Case-insensitive substring match on the page name. "
            "SQL ``%`` and ``_`` wildcards in the input are escaped."
        ),
        max_length=256,
    ),
) -> PaginatedList[schemas.ProjectPage]:
    results, count = await page_actions.list_for_project(
        session,
        auth_subject,
        project_id=project_id,
        parent_id=parent_id,
        include_archived=include_archived,
        name=name,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectPage.model_validate(p) for p in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Project Page",
    response_model=schemas.ProjectPage,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectPageID,
    auth_subject: auth.ProjectPagesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectPage:
    page = await page_actions.get(session, auth_subject, id)
    if page is None:
        raise ResourceNotFound()
    return schemas.ProjectPage.model_validate(page)


@router.post(
    "/",
    summary="Create Project Page",
    response_model=schemas.ProjectPage,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectPageCreate,
    auth_subject: auth.ProjectPagesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectPage:
    page = await page_actions.create(session, auth_subject, body)
    return schemas.ProjectPage.model_validate(page)


@router.patch(
    "/{id}",
    summary="Update Project Page",
    response_model=schemas.ProjectPage,
    responses={400: {}, 403: {}, 404: {}, 409: {}},
)
async def update(
    id: schemas.ProjectPageID,
    body: schemas.ProjectPageUpdate,
    auth_subject: auth.ProjectPagesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectPage:
    page = await page_actions.get(session, auth_subject, id)
    if page is None:
        raise ResourceNotFound()
    updated = await page_actions.update(session, auth_subject, page, body)
    return schemas.ProjectPage.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Project Page",
    status_code=204,
    responses={403: {}, 404: {}},
)
async def delete(
    id: schemas.ProjectPageID,
    auth_subject: auth.ProjectPagesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    page = await page_actions.get(session, auth_subject, id)
    if page is None:
        raise ResourceNotFound()
    await page_actions.delete(session, auth_subject, page)
