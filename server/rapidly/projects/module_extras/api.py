"""HTTP routes for module members and module external links."""

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
from rapidly.projects.module_extras import actions as me_actions
from rapidly.projects.module_extras import ordering
from rapidly.projects.module_extras import permissions as auth
from rapidly.projects.module_extras import types as schemas
from rapidly.routing import APIRouter

members_router = APIRouter(
    prefix="/project-module-members",
    tags=["project-module-members", APITag.public],
)
links_router = APIRouter(
    prefix="/project-module-links",
    tags=["project-module-links", APITag.public],
)


# ── Members ──────────────────────────────────────────────────────────


@members_router.get(
    "/",
    summary="List Project Module Members",
    response_model=PaginatedList[schemas.ProjectModuleMember],
)
async def list_members(
    auth_subject: auth.ModuleMembersRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ModuleExtrasSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    module_id: UUID = Query(
        ..., description="Required filter; returns members of this module."
    ),
) -> PaginatedList[schemas.ProjectModuleMember]:
    results, count = await me_actions.list_members(
        session,
        auth_subject,
        module_id=module_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectModuleMember.model_validate(m) for m in results],
        count,
        pagination,
    )


@members_router.post(
    "/",
    summary="Add Project Module Member",
    response_model=schemas.ProjectModuleMember,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def add_member(
    body: schemas.ProjectModuleMemberCreate,
    auth_subject: auth.ModuleMembersWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectModuleMember:
    member = await me_actions.add_member(session, auth_subject, body)
    return schemas.ProjectModuleMember.model_validate(member)


@members_router.delete(
    "/{id}",
    summary="Remove Project Module Member",
    status_code=204,
    responses={404: {}},
)
async def remove_member(
    id: schemas.ProjectModuleMemberID,
    auth_subject: auth.ModuleMembersWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    member = await me_actions.get_member(session, auth_subject, id)
    if member is None:
        raise ResourceNotFound()
    await me_actions.remove_member(session, auth_subject, member)


# ── Links ────────────────────────────────────────────────────────────


@links_router.get(
    "/",
    summary="List Project Module External Links",
    response_model=PaginatedList[schemas.ProjectModuleLink],
)
async def list_links(
    auth_subject: auth.ModuleLinksRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.ModuleExtrasSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    module_id: UUID = Query(
        ..., description="Required filter; returns links for this module."
    ),
) -> PaginatedList[schemas.ProjectModuleLink]:
    results, count = await me_actions.list_links(
        session,
        auth_subject,
        module_id=module_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectModuleLink.model_validate(link) for link in results],
        count,
        pagination,
    )


@links_router.post(
    "/",
    summary="Create Project Module External Link",
    response_model=schemas.ProjectModuleLink,
    status_code=201,
    responses={400: {}, 404: {}},
)
async def create_link(
    body: schemas.ProjectModuleLinkCreate,
    auth_subject: auth.ModuleLinksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectModuleLink:
    link = await me_actions.create_link(session, auth_subject, body)
    return schemas.ProjectModuleLink.model_validate(link)


@links_router.patch(
    "/{id}",
    summary="Update Project Module External Link",
    response_model=schemas.ProjectModuleLink,
    responses={400: {}, 404: {}},
)
async def update_link(
    id: schemas.ProjectModuleLinkID,
    body: schemas.ProjectModuleLinkUpdate,
    auth_subject: auth.ModuleLinksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectModuleLink:
    link = await me_actions.get_link(session, auth_subject, id)
    if link is None:
        raise ResourceNotFound()
    updated = await me_actions.update_link(session, auth_subject, link, body)
    return schemas.ProjectModuleLink.model_validate(updated)


@links_router.delete(
    "/{id}",
    summary="Delete Project Module External Link",
    status_code=204,
    responses={404: {}},
)
async def delete_link(
    id: schemas.ProjectModuleLinkID,
    auth_subject: auth.ModuleLinksWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    link = await me_actions.get_link(session, auth_subject, id)
    if link is None:
        raise ResourceNotFound()
    await me_actions.delete_link(session, auth_subject, link)
