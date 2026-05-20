"""HTTP routes for project-user-property (per-user view state)."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.user_property import actions as up_actions
from rapidly.projects.user_property import permissions as auth
from rapidly.projects.user_property import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/project-user-properties",
    tags=["project-user-properties", APITag.public],
)


@router.get(
    "/me",
    summary="Get My Project View Preferences",
    response_model=schemas.ProjectUserProperty,
    responses={404: {}},
)
async def get_mine(
    auth_subject: auth.UserPropertiesRead,
    project_id: UUID = Query(..., description="The project to fetch prefs for."),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectUserProperty:
    """Return the caller's preferences for the given project.

    Returns 404 when no preferences have been saved yet — the client
    is expected to fall back to defaults in that case.
    """
    record = await up_actions.get_mine_for_project(session, auth_subject, project_id)
    if record is None:
        raise ResourceNotFound()
    return schemas.ProjectUserProperty.model_validate(record)


@router.put(
    "/me",
    summary="Upsert My Project View Preferences",
    response_model=schemas.ProjectUserProperty,
    responses={404: {}},
)
async def upsert_mine(
    body: schemas.ProjectUserPropertyUpsert,
    auth_subject: auth.UserPropertiesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectUserProperty:
    record = await up_actions.upsert(session, auth_subject, body)
    return schemas.ProjectUserProperty.model_validate(record)
