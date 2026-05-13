"""Project HTTP routes: CRUD + archive/unarchive."""

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.project import actions as project_actions
from rapidly.projects.project import ordering
from rapidly.projects.project import permissions as auth
from rapidly.projects.project import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/projects", tags=["projects", APITag.public])


# ── List ──


@router.get(
    "/",
    summary="List Projects",
    response_model=PaginatedList[schemas.Project],
)
async def list(
    auth_subject: auth.ProjectsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    include_archived: bool = Query(
        False, description="Include archived projects in the result set."
    ),
    name: str | None = Query(
        None,
        description=(
            "Case-insensitive substring match on the project display name. "
            "SQL ``%`` and ``_`` wildcards in the input are escaped."
        ),
        max_length=256,
    ),
) -> PaginatedList[schemas.Project]:
    results, count = await project_actions.list(
        session,
        auth_subject,
        workspace_id=workspace_id,
        include_archived=include_archived,
        name=name,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.Project.model_validate(p) for p in results], count, pagination
    )


# ── Get ──


@router.get(
    "/{id}",
    summary="Get Project",
    response_model=schemas.Project,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectID,
    auth_subject: auth.ProjectsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.Project:
    project = await project_actions.get(session, auth_subject, id)
    if project is None:
        raise ResourceNotFound()
    return schemas.Project.model_validate(project)


# ── Create ──


@router.post(
    "/",
    summary="Create Project",
    response_model=schemas.Project,
    status_code=201,
    responses={409: {}},
)
async def create(
    body: schemas.ProjectCreate,
    auth_subject: auth.ProjectsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.Project:
    project = await project_actions.create(
        session, auth_subject, body.workspace_id, body
    )
    return schemas.Project.model_validate(project)


# ── Update ──


@router.patch(
    "/{id}",
    summary="Update Project",
    response_model=schemas.Project,
    responses={404: {}},
)
async def update(
    id: schemas.ProjectID,
    body: schemas.ProjectUpdate,
    auth_subject: auth.ProjectsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.Project:
    project = await project_actions.get(session, auth_subject, id)
    if project is None:
        raise ResourceNotFound()
    updated = await project_actions.update(session, auth_subject, project, body)
    return schemas.Project.model_validate(updated)


# ── Archive / Unarchive ──


@router.post(
    "/{id}/archive",
    summary="Archive Project",
    response_model=schemas.Project,
    responses={404: {}},
)
async def archive(
    id: schemas.ProjectID,
    auth_subject: auth.ProjectsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.Project:
    project = await project_actions.get(session, auth_subject, id)
    if project is None:
        raise ResourceNotFound()
    archived = await project_actions.archive(session, auth_subject, project)
    return schemas.Project.model_validate(archived)


@router.post(
    "/{id}/unarchive",
    summary="Unarchive Project",
    response_model=schemas.Project,
    responses={404: {}},
)
async def unarchive(
    id: schemas.ProjectID,
    auth_subject: auth.ProjectsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.Project:
    project = await project_actions.get(session, auth_subject, id)
    if project is None:
        raise ResourceNotFound()
    restored = await project_actions.unarchive(session, auth_subject, project)
    return schemas.Project.model_validate(restored)


# ── Delete ──


@router.delete(
    "/{id}",
    summary="Delete Project",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.ProjectID,
    auth_subject: auth.ProjectsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    project = await project_actions.get(session, auth_subject, id)
    if project is None:
        raise ResourceNotFound()
    await project_actions.delete(session, auth_subject, project)
