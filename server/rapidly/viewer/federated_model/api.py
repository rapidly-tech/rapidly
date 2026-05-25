"""HTTP endpoints for federated 3D models (``/api/v1/federated-models/*``).

The IfcOpenShell parser worker that flips status='uploaded' →
'parsing' → 'ready' ships in M3.1b. Until then ``POST`` creates a
row in status='uploaded' that the future worker will pick up; the
frontend can poll ``GET /{id}`` and render a "parsing pending"
state.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Query, status

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter
from rapidly.viewer.federated_model import actions
from rapidly.viewer.federated_model.permissions import (
    FederatedModelsRead,
    FederatedModelsWrite,
)
from rapidly.viewer.federated_model.types import (
    FederatedModelCreate,
    FederatedModelSchema,
    XktDownloadUrlSchema,
)

router = APIRouter(
    prefix="/v1/federated-models",
    tags=["federated-models", APITag.private],
)


@router.get(
    "/",
    summary="List Federated Models",
    response_model=PaginatedList[FederatedModelSchema],
)
async def list_models(
    auth_subject: FederatedModelsRead,
    pagination: PaginationParamsQuery,
    project_id: UUID | None = Query(None),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[FederatedModelSchema]:
    results, count = await actions.list_models(
        session,
        auth_subject,
        project_id=project_id,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get(
    "/{id}",
    summary="Get Federated Model",
    response_model=FederatedModelSchema,
)
async def get_model(
    id: UUID,
    auth_subject: FederatedModelsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> FederatedModelSchema:
    model = await actions.get_or_raise(session, auth_subject, id)
    return FederatedModelSchema.model_validate(model)


@router.post(
    "/",
    summary="Create Federated Model",
    response_model=FederatedModelSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_model(
    body: FederatedModelCreate,
    auth_subject: FederatedModelsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> FederatedModelSchema:
    model = await actions.create(session, auth_subject, body)
    return FederatedModelSchema.model_validate(model)


@router.get(
    "/{id}/xkt-url",
    summary="Get XKT Download URL",
    response_model=XktDownloadUrlSchema,
)
async def get_xkt_url(
    id: UUID,
    auth_subject: FederatedModelsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> XktDownloadUrlSchema:
    """Return a presigned URL the frontend viewer fetches the XKT
    bytes from. URLs are short-lived; the viewer re-calls this if
    the cached URL expires.
    """
    model = await actions.get_or_raise(session, auth_subject, id)
    url, expires_at = await actions.get_xkt_download_url(session, model)
    return XktDownloadUrlSchema(url=url, expires_at=expires_at)


@router.delete(
    "/{id}",
    summary="Delete Federated Model",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_model(
    id: UUID,
    auth_subject: FederatedModelsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    model = await actions.get_or_raise(session, auth_subject, id)
    await actions.delete(session, auth_subject, model)
