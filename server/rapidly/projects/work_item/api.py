"""Work-item HTTP routes: CRUD with assignee/label reconciliation."""

# Required so list[...] annotations remain the builtin even though
# ``list`` is shadowed by the route-handler function below.
from __future__ import annotations

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
from rapidly.projects.work_item import actions as work_item_actions
from rapidly.projects.work_item import ordering
from rapidly.projects.work_item import permissions as auth
from rapidly.projects.work_item import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/work-items", tags=["work-items", APITag.public])


async def _to_schema(
    session: AsyncReadSession | AsyncSession,
    work_item: schemas.WorkItem | object,
) -> schemas.WorkItem:
    """Materialise a WorkItem ORM row + its assignee and label IDs."""
    from rapidly.models import WorkItem as WorkItemModel

    if not isinstance(work_item, WorkItemModel):
        # Defensive — ``response_model`` already enforces shape.
        return schemas.WorkItem.model_validate(work_item)
    assignee_ids = await work_item_actions.get_assignee_ids(session, work_item.id)
    label_ids = await work_item_actions.get_label_ids(session, work_item.id)
    payload = schemas.WorkItem.model_validate(work_item)
    payload.assignee_ids = list(assignee_ids)
    payload.label_ids = list(label_ids)
    return payload


# ── List ──


@router.get(
    "/",
    summary="List Work Items",
    response_model=PaginatedList[schemas.WorkItem],
)
async def list_items(
    auth_subject: auth.WorkItemsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by project ID."
    ),
    state_id: MultipleQueryFilter[UUID] | None = Query(
        None, description="Filter by state ID."
    ),
    parent_id: UUID | None = Query(
        None, description="Filter to work items whose parent is this ID."
    ),
    include_archived: bool = Query(False, description="Include archived work items."),
    include_drafts: bool = Query(False, description="Include drafts."),
    assigned_to_me: bool = Query(
        False,
        description=(
            "Restrict to work items assigned to the calling user. "
            "Rejected for workspace tokens."
        ),
    ),
) -> PaginatedList[schemas.WorkItem]:
    results, count = await work_item_actions.list_items(
        session,
        auth_subject,
        project_id=project_id,
        state_id=state_id,
        parent_id=parent_id,
        include_archived=include_archived,
        include_drafts=include_drafts,
        assigned_to_me=assigned_to_me,
        pagination=pagination,
        sorting=sorting,
    )
    schemas_list = [await _to_schema(session, w) for w in results]
    return PaginatedList.from_paginated_results(schemas_list, count, pagination)


# ── Get ──


@router.get(
    "/{id}",
    summary="Get Work Item",
    response_model=schemas.WorkItem,
    responses={404: {}},
)
async def get(
    id: schemas.WorkItemID,
    auth_subject: auth.WorkItemsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.WorkItem:
    work_item = await work_item_actions.get(session, auth_subject, id)
    if work_item is None:
        raise ResourceNotFound()
    return await _to_schema(session, work_item)


# ── Create ──


@router.post(
    "/",
    summary="Create Work Item",
    response_model=schemas.WorkItem,
    status_code=201,
    responses={400: {}, 404: {}},
)
async def create(
    body: schemas.WorkItemCreate,
    auth_subject: auth.WorkItemsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItem:
    work_item = await work_item_actions.create(session, auth_subject, body)
    return await _to_schema(session, work_item)


# ── Update ──


@router.patch(
    "/{id}",
    summary="Update Work Item",
    response_model=schemas.WorkItem,
    responses={400: {}, 404: {}},
)
async def update(
    id: schemas.WorkItemID,
    body: schemas.WorkItemUpdate,
    auth_subject: auth.WorkItemsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItem:
    work_item = await work_item_actions.get(session, auth_subject, id)
    if work_item is None:
        raise ResourceNotFound()
    updated = await work_item_actions.update(session, auth_subject, work_item, body)
    return await _to_schema(session, updated)


# ── Delete ──


@router.delete(
    "/{id}",
    summary="Delete Work Item",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.WorkItemID,
    auth_subject: auth.WorkItemsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    work_item = await work_item_actions.get(session, auth_subject, id)
    if work_item is None:
        raise ResourceNotFound()
    await work_item_actions.delete(session, auth_subject, work_item)
