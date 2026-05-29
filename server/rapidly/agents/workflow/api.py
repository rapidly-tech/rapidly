"""HTTP endpoints for workflows (``/api/v1/workflows/*``)."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Query, status

from rapidly.agents.workflow import actions
from rapidly.agents.workflow.permissions import WorkflowsRead, WorkflowsWrite
from rapidly.agents.workflow.types import (
    WorkflowCreate,
    WorkflowSchema,
    WorkflowUpdate,
)
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

router = APIRouter(prefix="/v1/workflows", tags=["workflows", APITag.private])


@router.get(
    "/",
    summary="List Workflows",
    response_model=PaginatedList[WorkflowSchema],
)
async def list_workflows(
    auth_subject: WorkflowsRead,
    pagination: PaginationParamsQuery,
    workspace_id: UUID | None = Query(
        None,
        description=(
            "Narrow to a single workspace. The caller still needs read "
            "access to that workspace; unknown IDs return an empty set "
            "rather than 403 so we don't leak membership."
        ),
    ),
    project_id: UUID | None = Query(None),
    name: str | None = Query(
        None,
        description=(
            "Case-insensitive substring match on the display name. "
            "SQL ``%`` and ``_`` wildcards in the input are escaped."
        ),
        max_length=256,
    ),
    has_version: bool | None = Query(
        None,
        description=(
            "Filter by whether the workflow has a published version. "
            "``true`` → only workflows with current_version_id set; "
            "``false`` → only drafts; omitted → both."
        ),
    ),
    is_archived: bool | None = Query(
        False,
        description=(
            "Filter by archive state. ``false`` (default) hides archived "
            "rows; ``true`` returns archived-only; ``null`` (omit) returns "
            "both. Archived workflows still resolve in run history — the "
            "list endpoint just hides them so the catalog stays focused."
        ),
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[WorkflowSchema]:
    results, count = await actions.list_workflows(
        session,
        auth_subject,
        workspace_id=workspace_id,
        project_id=project_id,
        name=name,
        has_version=has_version,
        is_archived=is_archived,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get(
    "/{id}",
    summary="Get Workflow",
    response_model=WorkflowSchema,
)
async def get_workflow(
    id: UUID,
    auth_subject: WorkflowsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> WorkflowSchema:
    workflow = await actions.get_or_raise(session, auth_subject, id)
    return WorkflowSchema.model_validate(workflow)


@router.post(
    "/",
    summary="Create Workflow",
    response_model=WorkflowSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    body: WorkflowCreate,
    auth_subject: WorkflowsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowSchema:
    workflow = await actions.create(session, auth_subject, body)
    return WorkflowSchema.model_validate(workflow)


@router.patch(
    "/{id}",
    summary="Update Workflow",
    response_model=WorkflowSchema,
)
async def update_workflow(
    id: UUID,
    body: WorkflowUpdate,
    auth_subject: WorkflowsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowSchema:
    workflow = await actions.get_or_raise(session, auth_subject, id)
    updated = await actions.update(session, auth_subject, workflow, body)
    return WorkflowSchema.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Workflow",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workflow(
    id: UUID,
    auth_subject: WorkflowsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    workflow = await actions.get_or_raise(session, auth_subject, id)
    await actions.delete(session, auth_subject, workflow)


@router.post(
    "/{id}/archive",
    summary="Archive Workflow",
    response_model=WorkflowSchema,
    description=(
        "Stamp ``archived_at = now()``. Idempotent — archiving an "
        "already-archived workflow returns the row unchanged. The "
        "workflow stays queryable so past runs can resolve their "
        "parent, but the list endpoint hides it by default."
    ),
)
async def archive_workflow(
    id: UUID,
    auth_subject: WorkflowsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowSchema:
    workflow = await actions.get_or_raise(session, auth_subject, id)
    archived = await actions.archive(session, auth_subject, workflow)
    return WorkflowSchema.model_validate(archived)


@router.post(
    "/{id}/unarchive",
    summary="Unarchive Workflow",
    response_model=WorkflowSchema,
    description=("Clear ``archived_at``. Idempotent on already-active rows."),
)
async def unarchive_workflow(
    id: UUID,
    auth_subject: WorkflowsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowSchema:
    workflow = await actions.get_or_raise(session, auth_subject, id)
    unarchived = await actions.unarchive(session, auth_subject, workflow)
    return WorkflowSchema.model_validate(unarchived)
