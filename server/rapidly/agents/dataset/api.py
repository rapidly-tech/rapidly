"""HTTP endpoints for datasets + cases.

``/api/v1/agents/datasets/*`` + nested
``/api/v1/agents/datasets/{id}/cases/*``
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Query, status

from rapidly.agents.dataset import actions
from rapidly.agents.dataset.permissions import DatasetsRead, DatasetsWrite
from rapidly.agents.dataset.types import (
    DatasetCaseCreate,
    DatasetCaseSchema,
    DatasetCaseUpdate,
    DatasetCreate,
    DatasetSchema,
    DatasetUpdate,
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

router = APIRouter(prefix="/v1/agents/datasets", tags=["datasets", APITag.private])


# ── Datasets ───────────────────────────────────────────────


@router.get(
    "/",
    summary="List Datasets",
    response_model=PaginatedList[DatasetSchema],
)
async def list_datasets(
    auth_subject: DatasetsRead,
    pagination: PaginationParamsQuery,
    name: str | None = Query(
        None,
        description=(
            "Case-insensitive substring match on the display name. "
            "SQL ``%`` and ``_`` wildcards in the input are escaped."
        ),
        max_length=256,
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[DatasetSchema]:
    results, count = await actions.list_datasets(
        session, auth_subject, name=name, pagination=pagination
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get("/{id}", summary="Get Dataset", response_model=DatasetSchema)
async def get_dataset(
    id: UUID,
    auth_subject: DatasetsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> DatasetSchema:
    dataset = await actions.get_dataset_or_raise(session, auth_subject, id)
    return DatasetSchema.model_validate(dataset)


@router.post(
    "/",
    summary="Create Dataset",
    response_model=DatasetSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    body: DatasetCreate,
    auth_subject: DatasetsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> DatasetSchema:
    dataset = await actions.create_dataset(session, auth_subject, body)
    return DatasetSchema.model_validate(dataset)


@router.patch(
    "/{id}",
    summary="Update Dataset",
    response_model=DatasetSchema,
)
async def update_dataset(
    id: UUID,
    body: DatasetUpdate,
    auth_subject: DatasetsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> DatasetSchema:
    dataset = await actions.get_dataset_or_raise(session, auth_subject, id)
    updated = await actions.update_dataset(session, auth_subject, dataset, body)
    return DatasetSchema.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Dataset",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dataset(
    id: UUID,
    auth_subject: DatasetsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    dataset = await actions.get_dataset_or_raise(session, auth_subject, id)
    await actions.delete_dataset(session, auth_subject, dataset)


# ── Cases (nested under datasets) ──────────────────────────


@router.get(
    "/{dataset_id}/cases",
    summary="List Dataset Cases",
    response_model=list[DatasetCaseSchema],
)
async def list_cases(
    dataset_id: UUID,
    auth_subject: DatasetsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> list[DatasetCaseSchema]:
    dataset = await actions.get_dataset_or_raise(session, auth_subject, dataset_id)
    rows = await actions.list_cases(session, auth_subject, dataset)
    return [DatasetCaseSchema.model_validate(c) for c in rows]


@router.post(
    "/{dataset_id}/cases",
    summary="Create Dataset Case",
    response_model=DatasetCaseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_case(
    dataset_id: UUID,
    body: DatasetCaseCreate,
    auth_subject: DatasetsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> DatasetCaseSchema:
    dataset = await actions.get_dataset_or_raise(session, auth_subject, dataset_id)
    case = await actions.create_case(session, dataset, body)
    return DatasetCaseSchema.model_validate(case)


@router.patch(
    "/{dataset_id}/cases/{case_id}",
    summary="Update Dataset Case",
    response_model=DatasetCaseSchema,
)
async def update_case(
    dataset_id: UUID,
    case_id: UUID,
    body: DatasetCaseUpdate,
    auth_subject: DatasetsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> DatasetCaseSchema:
    dataset = await actions.get_dataset_or_raise(session, auth_subject, dataset_id)
    case = await actions.get_case_or_raise(session, dataset, case_id)
    updated = await actions.update_case(session, case, body)
    return DatasetCaseSchema.model_validate(updated)


@router.delete(
    "/{dataset_id}/cases/{case_id}",
    summary="Delete Dataset Case",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_case(
    dataset_id: UUID,
    case_id: UUID,
    auth_subject: DatasetsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    dataset = await actions.get_dataset_or_raise(session, auth_subject, dataset_id)
    case = await actions.get_case_or_raise(session, dataset, case_id)
    await actions.delete_case(session, case)
