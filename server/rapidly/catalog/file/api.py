"""File HTTP endpoints: upload, completion, download, update, and deletion.

Exposes pre-signed upload URLs, multipart upload completion, metadata
updates, and file deletion for workspace-scoped file management.
"""

from typing import Annotated

from fastapi import Depends, Path, Query
from pydantic import UUID4

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.core.types import MultipleQueryFilter
from rapidly.errors import NotPermitted, ResourceNotFound
from rapidly.models import File
from rapidly.openapi import APITag
from rapidly.platform.workspace.resolver import get_payload_workspace
from rapidly.platform.workspace.types import WorkspaceID
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

from . import actions as file_service
from . import permissions as auth
from .types import (
    FileCreate,
    FilePatch,
    FileRead,
    FileReadAdapter,
    FileUpload,
    FileUploadCompleted,
)

router = APIRouter(prefix="/files", tags=["files", APITag.public])

FileID = Annotated[UUID4, Path(description="The file ID.")]
FileNotFound = {"description": "File not found.", "model": ResourceNotFound.schema()}


# ---------------------------------------------------------------------------
# Upload lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=FileUpload,
    summary="Create File",
    status_code=201,
    responses={201: {"description": "File created."}},
)
async def create(
    file_create: FileCreate,
    auth_subject: auth.FileWrite,
    session: AsyncSession = Depends(get_db_session),
) -> FileUpload:
    """Initiate a file upload by requesting pre-signed URLs."""
    workspace = await get_payload_workspace(session, auth_subject, file_create)

    file_create.workspace_id = workspace.id
    return await file_service.generate_presigned_upload(
        session,
        workspace=workspace,
        create_schema=file_create,
    )


@router.post(
    "/{id}/uploaded",
    summary="Complete File Upload",
    response_model=FileRead,
    responses={
        200: {"description": "File upload completed."},
        403: {
            "description": "You don't have the permission to update this file.",
            "model": NotPermitted.schema(),
        },
        404: FileNotFound,
    },
)
async def uploaded(
    id: FileID,
    completed_schema: FileUploadCompleted,
    auth_subject: auth.FileWrite,
    session: AsyncSession = Depends(get_db_session),
) -> File:
    """Mark a file upload as completed."""
    found = await file_service.get(session, auth_subject, id)
    if found is None:
        raise ResourceNotFound()

    return await file_service.complete_upload(
        session, file=found, completed_schema=completed_schema
    )


# ---------------------------------------------------------------------------
# Metadata queries
# ---------------------------------------------------------------------------


@router.get("/", summary="List Files", response_model=PaginatedList[FileRead])
async def list(
    auth_subject: auth.FileRead,
    pagination: PaginationParamsQuery,
    workspace_id: MultipleQueryFilter[WorkspaceID] | None = Query(
        None, title="WorkspaceID Filter", description="Filter by workspace ID."
    ),
    ids: MultipleQueryFilter[UUID4] | None = Query(
        None, title="FileID Filter", description="Filter by file ID."
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[FileRead]:
    """List files."""
    results, count = await file_service.list(
        session,
        auth_subject,
        workspace_id=workspace_id,
        ids=ids,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(
        [FileReadAdapter.validate_python(r) for r in results],
        count,
        pagination,
    )


# ---------------------------------------------------------------------------
# Update & Delete
# ---------------------------------------------------------------------------


@router.patch(
    "/{id}",
    summary="Update File",
    response_model=FileRead,
    responses={
        200: {"description": "File updated."},
        403: {
            "description": "You don't have the permission to update this file.",
            "model": NotPermitted.schema(),
        },
        404: FileNotFound,
    },
)
async def update(
    auth_subject: auth.FileWrite,
    id: FileID,
    patches: FilePatch,
    session: AsyncSession = Depends(get_db_session),
) -> File:
    """Update a file."""
    found = await file_service.get(session, auth_subject, id)
    if found is None:
        raise ResourceNotFound()

    return await file_service.patch(session, file=found, patches=patches)


@router.delete(
    "/{id}",
    summary="Delete File",
    status_code=204,
    responses={
        204: {"description": "File deleted."},
        403: {
            "description": "You don't have the permission to delete this file.",
            "model": NotPermitted.schema(),
        },
        404: FileNotFound,
    },
)
async def delete(
    auth_subject: auth.FileWrite,
    id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a file."""
    found = await file_service.get(session, auth_subject, id)
    if found is None:
        raise ResourceNotFound()

    await file_service.delete(session, file=found)
