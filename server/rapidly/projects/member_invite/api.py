"""HTTP routes for project-member invites."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import ResourceNotFound
from rapidly.models import ProjectMemberInviteStatus
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.member_invite import actions as invite_actions
from rapidly.projects.member_invite import ordering
from rapidly.projects.member_invite import permissions as auth
from rapidly.projects.member_invite import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/project-member-invites",
    tags=["project-member-invites", APITag.public],
)


@router.get(
    "/",
    summary="List Project Member Invites",
    response_model=PaginatedList[schemas.ProjectMemberInvite],
)
async def list(
    auth_subject: auth.InvitesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ProjectMemberInvitesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
    invitee_id: UUID | None = Query(None, description="Filter by invitee user ID."),
    status: ProjectMemberInviteStatus | None = Query(
        None, description="Filter by invite status."
    ),
) -> PaginatedList[schemas.ProjectMemberInvite]:
    results, count = await invite_actions.list_for_project(
        session,
        auth_subject,
        project_id=project_id,
        invitee_id=invitee_id,
        status=status,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectMemberInvite.model_validate(i) for i in results],
        count,
        pagination,
    )


@router.post(
    "/",
    summary="Invite to Project",
    response_model=schemas.ProjectMemberInvite,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectMemberInviteCreate,
    auth_subject: auth.InvitesAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectMemberInvite:
    invite = await invite_actions.create(session, auth_subject, body)
    return schemas.ProjectMemberInvite.model_validate(invite)


@router.post(
    "/accept",
    summary="Accept Project Member Invite",
    response_model=schemas.AcceptedInviteResponse,
    responses={403: {}, 404: {}},
)
async def accept(
    body: schemas.ProjectMemberInviteAccept,
    auth_subject: auth.InvitesSelf,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.AcceptedInviteResponse:
    member = await invite_actions.accept(session, auth_subject, token=body.token)
    return schemas.AcceptedInviteResponse(
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
    )


@router.post(
    "/{id}/decline",
    summary="Decline Project Member Invite",
    response_model=schemas.ProjectMemberInvite,
    responses={400: {}, 403: {}, 404: {}},
)
async def decline(
    id: schemas.ProjectMemberInviteID,
    auth_subject: auth.InvitesSelf,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectMemberInvite:
    invite = await invite_actions.get(session, auth_subject, id)
    if invite is None:
        raise ResourceNotFound()
    declined = await invite_actions.decline(session, auth_subject, invite)
    return schemas.ProjectMemberInvite.model_validate(declined)


@router.post(
    "/{id}/revoke",
    summary="Revoke Project Member Invite",
    response_model=schemas.ProjectMemberInvite,
    responses={400: {}, 404: {}},
)
async def revoke(
    id: schemas.ProjectMemberInviteID,
    auth_subject: auth.InvitesAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectMemberInvite:
    invite = await invite_actions.get(session, auth_subject, id)
    if invite is None:
        raise ResourceNotFound()
    revoked = await invite_actions.revoke(session, auth_subject, invite)
    return schemas.ProjectMemberInvite.model_validate(revoked)
