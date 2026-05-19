"""HTTP routes for project members."""

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
from rapidly.projects.member import actions as member_actions
from rapidly.projects.member import ordering
from rapidly.projects.member import permissions as auth
from rapidly.projects.member import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/project-members", tags=["project-members", APITag.public])


@router.get(
    "/",
    summary="List Project Members",
    response_model=PaginatedList[schemas.ProjectMember],
)
async def list(
    auth_subject: auth.ProjectMembersRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectMembersSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
) -> PaginatedList[schemas.ProjectMember]:
    results, count = await member_actions.list_for_project(
        session,
        auth_subject,
        project_id=project_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectMember.model_validate(m) for m in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Project Member",
    response_model=schemas.ProjectMember,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectMemberID,
    auth_subject: auth.ProjectMembersRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectMember:
    member = await member_actions.get(session, auth_subject, id)
    if member is None:
        raise ResourceNotFound()
    return schemas.ProjectMember.model_validate(member)


@router.post(
    "/",
    summary="Add Project Member",
    response_model=schemas.ProjectMember,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectMemberCreate,
    auth_subject: auth.ProjectMembersWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectMember:
    member = await member_actions.create(session, auth_subject, body)
    return schemas.ProjectMember.model_validate(member)


@router.patch(
    "/{id}",
    summary="Update Project Member",
    response_model=schemas.ProjectMember,
    responses={400: {}, 404: {}},
)
async def update(
    id: schemas.ProjectMemberID,
    body: schemas.ProjectMemberUpdate,
    auth_subject: auth.ProjectMembersWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectMember:
    member = await member_actions.get(session, auth_subject, id)
    if member is None:
        raise ResourceNotFound()
    updated = await member_actions.update(session, auth_subject, member, body)
    return schemas.ProjectMember.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Remove Project Member",
    status_code=204,
    responses={400: {}, 404: {}},
)
async def delete(
    id: schemas.ProjectMemberID,
    auth_subject: auth.ProjectMembersWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    member = await member_actions.get(session, auth_subject, id)
    if member is None:
        raise ResourceNotFound()
    await member_actions.delete(session, auth_subject, member)
