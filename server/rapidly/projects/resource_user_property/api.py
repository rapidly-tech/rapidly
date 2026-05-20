"""HTTP routes for cycle/module per-user view state."""

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
from rapidly.projects.resource_user_property import actions as up_actions
from rapidly.projects.resource_user_property import permissions as auth
from rapidly.projects.resource_user_property import types as schemas
from rapidly.routing import APIRouter

cycle_router = APIRouter(
    prefix="/project-cycle-user-properties",
    tags=["project-cycle-user-properties", APITag.public],
)
module_router = APIRouter(
    prefix="/project-module-user-properties",
    tags=["project-module-user-properties", APITag.public],
)


# ── Cycles ───────────────────────────────────────────────────────────


@cycle_router.get(
    "/me",
    summary="Get My Cycle View Preferences",
    response_model=schemas.ProjectCycleUserProperty,
    responses={404: {}},
)
async def get_cycle_mine(
    auth_subject: auth.CyclePropsRead,
    cycle_id: UUID = Query(..., description="The cycle to fetch prefs for."),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectCycleUserProperty:
    record = await up_actions.get_cycle_props(session, auth_subject, cycle_id)
    if record is None:
        raise ResourceNotFound()
    return schemas.ProjectCycleUserProperty.model_validate(record)


@cycle_router.put(
    "/me",
    summary="Upsert My Cycle View Preferences",
    response_model=schemas.ProjectCycleUserProperty,
    responses={404: {}},
)
async def upsert_cycle_mine(
    body: schemas.ProjectCycleUserPropertyUpsert,
    auth_subject: auth.CyclePropsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectCycleUserProperty:
    record = await up_actions.upsert_cycle_props(session, auth_subject, body)
    return schemas.ProjectCycleUserProperty.model_validate(record)


# ── Modules ──────────────────────────────────────────────────────────


@module_router.get(
    "/me",
    summary="Get My Module View Preferences",
    response_model=schemas.ProjectModuleUserProperty,
    responses={404: {}},
)
async def get_module_mine(
    auth_subject: auth.ModulePropsRead,
    module_id: UUID = Query(..., description="The module to fetch prefs for."),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectModuleUserProperty:
    record = await up_actions.get_module_props(session, auth_subject, module_id)
    if record is None:
        raise ResourceNotFound()
    return schemas.ProjectModuleUserProperty.model_validate(record)


@module_router.put(
    "/me",
    summary="Upsert My Module View Preferences",
    response_model=schemas.ProjectModuleUserProperty,
    responses={404: {}},
)
async def upsert_module_mine(
    body: schemas.ProjectModuleUserPropertyUpsert,
    auth_subject: auth.ModulePropsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectModuleUserProperty:
    record = await up_actions.upsert_module_props(session, auth_subject, body)
    return schemas.ProjectModuleUserProperty.model_validate(record)
