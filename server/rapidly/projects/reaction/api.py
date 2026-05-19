"""HTTP routes for emoji reactions on work items and comments."""

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
from rapidly.projects.reaction import actions as reaction_actions
from rapidly.projects.reaction import ordering
from rapidly.projects.reaction import permissions as auth
from rapidly.projects.reaction import types as schemas
from rapidly.routing import APIRouter

work_item_reactions_router = APIRouter(
    prefix="/work-item-reactions",
    tags=["work-item-reactions", APITag.public],
)
comment_reactions_router = APIRouter(
    prefix="/work-item-comment-reactions",
    tags=["work-item-comment-reactions", APITag.public],
)


# ── Work-item reactions ──────────────────────────────────────────────


@work_item_reactions_router.get(
    "/",
    summary="List Work Item Reactions",
    response_model=PaginatedList[schemas.WorkItemReaction],
)
async def list_work_item_reactions(
    auth_subject: auth.ReactionsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ReactionSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    work_item_id: UUID = Query(
        ..., description="Required filter; returns reactions for this work item."
    ),
) -> PaginatedList[schemas.WorkItemReaction]:
    results, count = await reaction_actions.list_work_item_reactions(
        session,
        auth_subject,
        work_item_id=work_item_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemReaction.model_validate(r) for r in results],
        count,
        pagination,
    )


@work_item_reactions_router.post(
    "/",
    summary="React to Work Item",
    response_model=schemas.WorkItemReaction,
    status_code=201,
    responses={404: {}, 409: {}},
)
async def react_to_work_item(
    body: schemas.WorkItemReactionCreate,
    auth_subject: auth.ReactionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemReaction:
    reaction = await reaction_actions.react_to_work_item(session, auth_subject, body)
    return schemas.WorkItemReaction.model_validate(reaction)


@work_item_reactions_router.delete(
    "/{id}",
    summary="Remove Work Item Reaction",
    status_code=204,
    responses={404: {}},
)
async def remove_work_item_reaction(
    id: schemas.WorkItemReactionID,
    auth_subject: auth.ReactionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    reaction = await reaction_actions.get_work_item_reaction(session, auth_subject, id)
    if reaction is None:
        raise ResourceNotFound()
    await reaction_actions.unreact_work_item(session, auth_subject, reaction)


# ── Comment reactions ────────────────────────────────────────────────


@comment_reactions_router.get(
    "/",
    summary="List Comment Reactions",
    response_model=PaginatedList[schemas.WorkItemCommentReaction],
)
async def list_comment_reactions(
    auth_subject: auth.ReactionsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ReactionSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    comment_id: UUID = Query(
        ..., description="Required filter; returns reactions for this comment."
    ),
) -> PaginatedList[schemas.WorkItemCommentReaction]:
    results, count = await reaction_actions.list_comment_reactions(
        session,
        auth_subject,
        comment_id=comment_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemCommentReaction.model_validate(r) for r in results],
        count,
        pagination,
    )


@comment_reactions_router.post(
    "/",
    summary="React to Comment",
    response_model=schemas.WorkItemCommentReaction,
    status_code=201,
    responses={404: {}, 409: {}},
)
async def react_to_comment(
    body: schemas.WorkItemCommentReactionCreate,
    auth_subject: auth.ReactionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemCommentReaction:
    reaction = await reaction_actions.react_to_comment(session, auth_subject, body)
    return schemas.WorkItemCommentReaction.model_validate(reaction)


@comment_reactions_router.delete(
    "/{id}",
    summary="Remove Comment Reaction",
    status_code=204,
    responses={404: {}},
)
async def remove_comment_reaction(
    id: schemas.WorkItemCommentReactionID,
    auth_subject: auth.ReactionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    reaction = await reaction_actions.get_comment_reaction(session, auth_subject, id)
    if reaction is None:
        raise ResourceNotFound()
    await reaction_actions.unreact_comment(session, auth_subject, reaction)
