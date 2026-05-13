"""Read-only HTTP routes for work-item activity."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.projects.activity import actions as activity_actions
from rapidly.projects.activity import ordering
from rapidly.projects.activity import permissions as auth
from rapidly.projects.activity import types as schemas
from rapidly.projects.work_item.queries import WorkItemRepository
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/work-item-activities", tags=["work-item-activities", APITag.public]
)


@router.get(
    "/",
    summary="List Work Item Activities",
    response_model=PaginatedList[schemas.WorkItemActivity],
    responses={404: {}},
)
async def list(
    auth_subject: auth.WorkItemActivitiesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemActivitiesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    work_item_id: UUID = Query(..., description="Required filter by work-item ID."),
) -> PaginatedList[schemas.WorkItemActivity]:
    # Confirm the caller can read the work item itself; missing visibility
    # there is a 404 (don't probe activity tables for items they can't see).
    work_item_repo = WorkItemRepository.from_session(session)
    work_item = await work_item_repo.get_one_or_none(
        work_item_repo.get_readable_statement(auth_subject).where(
            work_item_repo.model.id == work_item_id
        )
    )
    if work_item is None:
        raise ResourceNotFound()

    results, count = await activity_actions.list_for_work_item(
        session,
        auth_subject,
        work_item_id=work_item_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemActivity.model_validate(a) for a in results],
        count,
        pagination,
    )
