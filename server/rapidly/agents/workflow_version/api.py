"""HTTP endpoints for workflow versions.

Routes are nested under ``/workflows/{workflow_id}/versions/`` so
the URL structure matches the data model — versions belong to
exactly one workflow.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, status

from rapidly.agents.workflow import actions as workflow_actions
from rapidly.agents.workflow_version import actions
from rapidly.agents.workflow_version.permissions import (
    WorkflowVersionsRead,
    WorkflowVersionsWrite,
)
from rapidly.agents.workflow_version.types import (
    WorkflowVersionCreate,
    WorkflowVersionSchema,
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

router = APIRouter(
    prefix="/v1/workflows",
    tags=["workflow-versions", APITag.private],
)


@router.get(
    "/{workflow_id}/versions",
    summary="List Workflow Versions",
    response_model=PaginatedList[WorkflowVersionSchema],
)
async def list_versions(
    workflow_id: UUID,
    auth_subject: WorkflowVersionsRead,
    pagination: PaginationParamsQuery,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[WorkflowVersionSchema]:
    # 404 on the workflow first (cheaper than join + clearer error).
    await workflow_actions.get_or_raise(session, auth_subject, workflow_id)
    results, count = await actions.list_for_workflow(
        session,
        auth_subject,
        workflow_id=workflow_id,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get(
    "/{workflow_id}/versions/{version_id}",
    summary="Get Workflow Version",
    response_model=WorkflowVersionSchema,
)
async def get_version(
    workflow_id: UUID,
    version_id: UUID,
    auth_subject: WorkflowVersionsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> WorkflowVersionSchema:
    version = await actions.get_or_raise(session, auth_subject, version_id)
    if version.workflow_id != workflow_id:
        # Path mismatch — the version exists but doesn't belong to
        # the workflow in the URL. 404 not 403 so we don't leak the
        # version's existence to non-readers.
        from rapidly.errors import ResourceNotFound

        raise ResourceNotFound("Workflow version not found.")
    return WorkflowVersionSchema.model_validate(version)


@router.post(
    "/{workflow_id}/versions",
    summary="Publish Workflow Version",
    response_model=WorkflowVersionSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    workflow_id: UUID,
    body: WorkflowVersionCreate,
    auth_subject: WorkflowVersionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowVersionSchema:
    # Verify the workflow exists + is in our readable scope before
    # publishing. ``get_or_raise`` accepts a User|Workspace principal
    # but the version's write scope only allows User, so the
    # auth_subject is narrower than the workflow getter expects.
    # Re-cast at the call site — the readable filter is happy with
    # either.
    await workflow_actions.get_or_raise(session, auth_subject, workflow_id)
    version = await actions.create(
        session, auth_subject, workflow_id=workflow_id, data=body
    )
    return WorkflowVersionSchema.model_validate(version)
