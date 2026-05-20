"""HTTP routes for work-item votes."""

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
from rapidly.projects.vote import actions as vote_actions
from rapidly.projects.vote import ordering
from rapidly.projects.vote import permissions as auth
from rapidly.projects.vote import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/work-item-votes", tags=["work-item-votes", APITag.public])


@router.get(
    "/",
    summary="List Work Item Votes",
    response_model=PaginatedList[schemas.WorkItemVote],
)
async def list(
    auth_subject: auth.VotesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemVotesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    work_item_id: UUID = Query(
        ..., description="Required filter; returns votes for this work item."
    ),
) -> PaginatedList[schemas.WorkItemVote]:
    results, count = await vote_actions.list_for_work_item(
        session,
        auth_subject,
        work_item_id=work_item_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemVote.model_validate(v) for v in results],
        count,
        pagination,
    )


@router.post(
    "/",
    summary="Cast Vote on Work Item",
    response_model=schemas.WorkItemVote,
    status_code=201,
    responses={404: {}},
)
async def cast(
    body: schemas.WorkItemVoteCast,
    auth_subject: auth.VotesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemVote:
    vote = await vote_actions.cast(session, auth_subject, body)
    return schemas.WorkItemVote.model_validate(vote)


@router.delete(
    "/{id}",
    summary="Retract Vote",
    status_code=204,
    responses={404: {}},
)
async def retract(
    id: schemas.WorkItemVoteID,
    auth_subject: auth.VotesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    vote = await vote_actions.get(session, auth_subject, id)
    if vote is None:
        raise ResourceNotFound()
    await vote_actions.retract(session, auth_subject, vote)
