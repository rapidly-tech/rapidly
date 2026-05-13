"""Project label HTTP routes: CRUD."""

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
from rapidly.projects.label import actions as label_actions
from rapidly.projects.label import ordering
from rapidly.projects.label import permissions as auth
from rapidly.projects.label import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/project-labels", tags=["project-labels", APITag.public])


@router.get(
    "/",
    summary="List Project Labels",
    response_model=PaginatedList[schemas.ProjectLabel],
)
async def list(
    auth_subject: auth.ProjectLabelsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectLabelsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
    parent_id: UUID | None = Query(
        None, description="Filter labels with this parent ID."
    ),
    name: str | None = Query(
        None,
        description=(
            "Case-insensitive substring match on the label display name. "
            "SQL ``%`` and ``_`` wildcards in the input are escaped."
        ),
        max_length=256,
    ),
) -> PaginatedList[schemas.ProjectLabel]:
    results, count = await label_actions.list(
        session,
        auth_subject,
        project_id=project_id,
        parent_id=parent_id,
        name=name,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectLabel.model_validate(label) for label in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Project Label",
    response_model=schemas.ProjectLabel,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectLabelID,
    auth_subject: auth.ProjectLabelsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectLabel:
    label = await label_actions.get(session, auth_subject, id)
    if label is None:
        raise ResourceNotFound()
    return schemas.ProjectLabel.model_validate(label)


@router.post(
    "/",
    summary="Create Project Label",
    response_model=schemas.ProjectLabel,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectLabelCreate,
    auth_subject: auth.ProjectLabelsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectLabel:
    label = await label_actions.create(session, auth_subject, body)
    return schemas.ProjectLabel.model_validate(label)


@router.patch(
    "/{id}",
    summary="Update Project Label",
    response_model=schemas.ProjectLabel,
    responses={404: {}},
)
async def update(
    id: schemas.ProjectLabelID,
    body: schemas.ProjectLabelUpdate,
    auth_subject: auth.ProjectLabelsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectLabel:
    label = await label_actions.get(session, auth_subject, id)
    if label is None:
        raise ResourceNotFound()
    updated = await label_actions.update(session, auth_subject, label, body)
    return schemas.ProjectLabel.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Project Label",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.ProjectLabelID,
    auth_subject: auth.ProjectLabelsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    label = await label_actions.get(session, auth_subject, id)
    if label is None:
        raise ResourceNotFound()
    await label_actions.delete(session, auth_subject, label)
