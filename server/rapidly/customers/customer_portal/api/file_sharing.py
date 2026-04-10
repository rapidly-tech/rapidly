"""Customer portal endpoints for file sharing sessions."""

from typing import Annotated

from fastapi import Depends
from pydantic import UUID4

from rapidly.core.db.postgres import AsyncReadSession
from rapidly.core.ordering import Sorting, SortingGetter
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import get_db_read_session
from rapidly.routing import APIRouter
from rapidly.sharing.file_sharing.pg_repository import FileShareSessionSortProperty
from rapidly.sharing.file_sharing.types import (
    FileShareDownloadSchema,
    FileSharePaymentSchema,
    FileShareSessionSchema,
)

from .. import permissions as auth
from ..actions import file_sharing as file_sharing_actions

router = APIRouter(prefix="/file-sharing", tags=["file-sharing", APITag.public])

ListSorting = Annotated[
    list[Sorting[FileShareSessionSortProperty]],
    Depends(SortingGetter(FileShareSessionSortProperty, ["-created_at"])),
]


# ── Session Access ──


@router.get(
    "/sessions",
    summary="List File Sharing Sessions",
    response_model=PaginatedList[FileShareSessionSchema],
)
async def list_sessions(
    auth_subject: auth.CustomerPortalUnionRead,
    pagination: PaginationParamsQuery,
    sorting: ListSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[FileShareSessionSchema]:
    """List file sharing sessions for the authenticated member's workspace."""
    results, count = await file_sharing_actions.list_sessions(
        session, auth_subject, pagination=pagination, sorting=sorting
    )
    schemas = [FileShareSessionSchema.model_validate(r) for r in results]
    return PaginatedList.from_paginated_results(schemas, count, pagination)


@router.get(
    "/sessions/{id}",
    summary="Get File Sharing Session",
    response_model=FileShareSessionSchema,
    responses={
        404: {"description": "Session not found.", "model": ResourceNotFound.schema()}
    },
)
async def get_session(
    id: UUID4,
    auth_subject: auth.CustomerPortalUnionRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> FileShareSessionSchema:
    """Get a file sharing session by ID."""
    fs_session = await file_sharing_actions.get_session(
        session, auth_subject, session_id=id
    )
    if fs_session is None:
        raise ResourceNotFound()
    return FileShareSessionSchema.model_validate(fs_session)


# ── Download ──


@router.get(
    "/sessions/{id}/downloads",
    summary="List Session Downloads",
    response_model=list[FileShareDownloadSchema],
    responses={
        404: {"description": "Session not found.", "model": ResourceNotFound.schema()}
    },
)
async def list_session_downloads(
    id: UUID4,
    auth_subject: auth.CustomerPortalUnionRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> list[FileShareDownloadSchema]:
    """List downloads for a file sharing session."""
    downloads = await file_sharing_actions.list_session_downloads(
        session, auth_subject, session_id=id
    )
    if not downloads and not await file_sharing_actions.get_session(
        session, auth_subject, session_id=id
    ):
        raise ResourceNotFound()
    return [FileShareDownloadSchema.model_validate(d) for d in downloads]


@router.get(
    "/sessions/{id}/payments",
    summary="List Session Payments",
    response_model=list[FileSharePaymentSchema],
    responses={
        404: {"description": "Session not found.", "model": ResourceNotFound.schema()}
    },
)
async def list_session_payments(
    id: UUID4,
    auth_subject: auth.CustomerPortalUnionRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> list[FileSharePaymentSchema]:
    """List payments for a file sharing session."""
    payments = await file_sharing_actions.list_session_payments(
        session, auth_subject, session_id=id
    )
    if not payments and not await file_sharing_actions.get_session(
        session, auth_subject, session_id=id
    ):
        raise ResourceNotFound()
    return [FileSharePaymentSchema.model_validate(p) for p in payments]
