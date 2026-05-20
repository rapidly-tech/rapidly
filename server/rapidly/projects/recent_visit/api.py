"""HTTP routes for the per-user recent-visit feed."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import ResourceNotFound
from rapidly.models import RecentVisitEntityType
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.recent_visit import actions as rv_actions
from rapidly.projects.recent_visit import permissions as auth
from rapidly.projects.recent_visit import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/recent-visits", tags=["recent-visits", APITag.public])


@router.get(
    "/",
    summary="List My Recent Visits",
    response_model=PaginatedList[schemas.RecentVisit],
)
async def list(
    auth_subject: auth.RecentVisitsRead,
    pagination: PaginationParamsQuery,
    session: AsyncReadSession = Depends(get_db_read_session),
    workspace_id: UUID | None = Query(
        None, description="Optional filter — limit to a single workspace."
    ),
    entity_type: RecentVisitEntityType | None = Query(
        None, description="Optional filter — limit to one entity kind."
    ),
) -> PaginatedList[schemas.RecentVisit]:
    """Returns the caller's recently visited entities, newest first."""
    results, count = await rv_actions.list_mine(
        session,
        auth_subject,
        workspace_id=workspace_id,
        entity_type=entity_type,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(
        [schemas.RecentVisit.model_validate(r) for r in results],
        count,
        pagination,
    )


@router.post(
    "/",
    summary="Record a Visit",
    response_model=schemas.RecentVisit,
    status_code=201,
    responses={400: {}},
)
async def record(
    body: schemas.RecentVisitRecord,
    auth_subject: auth.RecentVisitsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.RecentVisit:
    """Bumps the visit row for ``(caller, entity_type, entity_id)`` to now,
    or inserts a new row if none exists."""
    visit = await rv_actions.record(session, auth_subject, body)
    return schemas.RecentVisit.model_validate(visit)


@router.delete(
    "/{id}",
    summary="Remove a Recent-Visit Entry",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.RecentVisitID,
    auth_subject: auth.RecentVisitsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    visit = await rv_actions.get(session, auth_subject, id)
    if visit is None:
        raise ResourceNotFound()
    await rv_actions.delete(session, auth_subject, visit)
