"""HTTP endpoints for IntegrationCredentials.

``/api/v1/agents/integration-credentials/*``

The API never returns plaintext secrets. Operators rotate by
``DELETE`` + ``POST``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Query, status

from rapidly.agents.integration_credential import actions
from rapidly.agents.integration_credential.permissions import (
    IntegrationCredentialsRead,
    IntegrationCredentialsWrite,
)
from rapidly.agents.integration_credential.types import (
    IntegrationCredentialCreate,
    IntegrationCredentialSchema,
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
    prefix="/v1/agents/integration-credentials",
    tags=["integration-credentials", APITag.private],
)


@router.get(
    "/",
    summary="List Integration Credentials",
    response_model=PaginatedList[IntegrationCredentialSchema],
)
async def list_credentials(
    auth_subject: IntegrationCredentialsRead,
    pagination: PaginationParamsQuery,
    provider: str | None = Query(None),
    name: str | None = Query(
        None,
        description=(
            "Case-insensitive substring match on the credential name. "
            "SQL ``%`` and ``_`` wildcards in the input are escaped."
        ),
        max_length=256,
    ),
    workspace_id: UUID | None = Query(
        None,
        description=(
            "Filter to a single workspace. The auth subject must "
            "already be readable for that workspace; otherwise the "
            "filter is a no-op against an empty visible set."
        ),
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[IntegrationCredentialSchema]:
    results, count = await actions.list_credentials(
        session,
        auth_subject,
        provider=provider,
        name=name,
        workspace_id=workspace_id,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get(
    "/{id}",
    summary="Get Integration Credential",
    response_model=IntegrationCredentialSchema,
)
async def get_credential(
    id: UUID,
    auth_subject: IntegrationCredentialsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> IntegrationCredentialSchema:
    record = await actions.get_or_raise(session, auth_subject, id)
    return IntegrationCredentialSchema.model_validate(record)


@router.post(
    "/",
    summary="Create Integration Credential",
    response_model=IntegrationCredentialSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_credential(
    body: IntegrationCredentialCreate,
    auth_subject: IntegrationCredentialsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationCredentialSchema:
    record = await actions.create(session, auth_subject, body)
    return IntegrationCredentialSchema.model_validate(record)


@router.post(
    "/{id}/default",
    summary="Set as Default",
    response_model=IntegrationCredentialSchema,
    description=(
        "Promote this credential to the default for its (workspace, "
        "provider) pair. Demotes any prior default in the same flush."
    ),
)
async def set_default(
    id: UUID,
    auth_subject: IntegrationCredentialsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationCredentialSchema:
    record = await actions.get_or_raise(session, auth_subject, id)
    updated = await actions.set_default(session, auth_subject, record)
    return IntegrationCredentialSchema.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Integration Credential",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_credential(
    id: UUID,
    auth_subject: IntegrationCredentialsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    record = await actions.get_or_raise(session, auth_subject, id)
    await actions.delete(session, auth_subject, record)
