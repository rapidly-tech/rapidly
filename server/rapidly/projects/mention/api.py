"""HTTP routes for work-item @mentions."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.mention import actions as mention_actions
from rapidly.projects.mention import ordering
from rapidly.projects.mention import permissions as auth
from rapidly.projects.mention import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/work-item-mentions", tags=["work-item-mentions", APITag.public]
)


@router.get(
    "/",
    summary="List Work Item Mentions",
    response_model=PaginatedList[schemas.WorkItemMention],
)
async def list(
    auth_subject: auth.MentionsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemMentionsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    work_item_id: UUID | None = Query(None, description="Filter by work item ID."),
    comment_id: UUID | None = Query(None, description="Filter by comment ID."),
    mentioned_user_id: UUID | None = Query(
        None,
        description=(
            "Filter by mentioned user ID. Combine with no other filter to "
            "fetch the 'mentions of me' feed."
        ),
    ),
) -> PaginatedList[schemas.WorkItemMention]:
    results, count = await mention_actions.list_mentions(
        session,
        auth_subject,
        work_item_id=work_item_id,
        comment_id=comment_id,
        mentioned_user_id=mentioned_user_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemMention.model_validate(m) for m in results],
        count,
        pagination,
    )


@router.post(
    "/",
    summary="Mention a User in a Comment",
    response_model=schemas.WorkItemMention,
    status_code=201,
    responses={400: {}, 403: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.WorkItemMentionCreate,
    auth_subject: auth.MentionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemMention:
    mention = await mention_actions.create(session, auth_subject, body)
    return schemas.WorkItemMention.model_validate(mention)


@router.delete(
    "/{id}",
    summary="Remove a Mention",
    status_code=204,
    responses={403: {}, 404: {}},
)
async def delete(
    id: schemas.WorkItemMentionID,
    auth_subject: auth.MentionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    mention = await mention_actions.get(session, auth_subject, id)
    if mention is None:
        raise ResourceNotFound()
    await mention_actions.delete(session, auth_subject, mention)
