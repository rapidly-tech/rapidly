"""HTTP endpoints for VectorCollections (``/api/v1/agents/vector-collections/*``).

Surface:
    GET    /v1/agents/vector-collections        — list, paginated
    GET    /v1/agents/vector-collections/{id}   — read
    POST   /v1/agents/vector-collections        — create
    PATCH  /v1/agents/vector-collections/{id}   — update (name/project_id only)
    DELETE /v1/agents/vector-collections/{id}   — soft delete
    POST   /v1/agents/vector-collections/{id}/index — trigger indexing
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Query, status

from rapidly.agents.vector_collection import actions
from rapidly.agents.vector_collection.permissions import (
    VectorCollectionsRead,
    VectorCollectionsWrite,
)
from rapidly.agents.vector_collection.types import (
    IndexRequest,
    IndexResponse,
    VectorCollectionCreate,
    VectorCollectionSchema,
    VectorCollectionUpdate,
)
from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import NotPermitted
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/v1/agents/vector-collections",
    tags=["vector-collections", APITag.private],
)


@router.get(
    "/",
    summary="List Vector Collections",
    response_model=PaginatedList[VectorCollectionSchema],
)
async def list_collections(
    auth_subject: VectorCollectionsRead,
    pagination: PaginationParamsQuery,
    workspace_id: UUID | None = Query(
        None,
        description=(
            "Narrow to a single workspace. Unknown IDs return an empty "
            "set rather than 403 so we don't leak membership."
        ),
    ),
    project_id: UUID | None = Query(None),
    name: str | None = Query(
        None,
        description=(
            "Case-insensitive substring match on the collection name. "
            "SQL ``%`` and ``_`` wildcards in the input are escaped."
        ),
        max_length=256,
    ),
    is_archived: bool | None = Query(
        None,
        description=(
            "Filter by archive state. ``false`` → only active collections; "
            "``true`` → only archived; omitted → both. The frontend "
            "vector-collections page defaults to ``false`` to keep the "
            "catalog focused; direct API users get both unless they narrow."
        ),
    ),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> PaginatedList[VectorCollectionSchema]:
    results, count = await actions.list_collections(
        session,
        auth_subject,
        workspace_id=workspace_id,
        project_id=project_id,
        name=name,
        is_archived=is_archived,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(results, count, pagination)


@router.get(
    "/{id}",
    summary="Get Vector Collection",
    response_model=VectorCollectionSchema,
)
async def get_collection(
    id: UUID,
    auth_subject: VectorCollectionsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> VectorCollectionSchema:
    collection = await actions.get_or_raise(session, auth_subject, id)
    return VectorCollectionSchema.model_validate(collection)


@router.post(
    "/",
    summary="Create Vector Collection",
    response_model=VectorCollectionSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection(
    body: VectorCollectionCreate,
    auth_subject: VectorCollectionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> VectorCollectionSchema:
    collection = await actions.create(session, auth_subject, body)
    return VectorCollectionSchema.model_validate(collection)


@router.patch(
    "/{id}",
    summary="Update Vector Collection",
    response_model=VectorCollectionSchema,
)
async def update_collection(
    id: UUID,
    body: VectorCollectionUpdate,
    auth_subject: VectorCollectionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> VectorCollectionSchema:
    collection = await actions.get_or_raise(session, auth_subject, id)
    updated = await actions.update(session, auth_subject, collection, body)
    return VectorCollectionSchema.model_validate(updated)


@router.delete(
    "/{id}",
    summary="Delete Vector Collection",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection(
    id: UUID,
    auth_subject: VectorCollectionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    collection = await actions.get_or_raise(session, auth_subject, id)
    await actions.delete(session, auth_subject, collection)


@router.post(
    "/{id}/archive",
    summary="Archive Vector Collection",
    response_model=VectorCollectionSchema,
    description=(
        "Stamp ``archived_at = now()``. Idempotent — archiving an "
        "already-archived collection returns the row unchanged. The "
        "collection stays queryable so RAG-search references that "
        "pointed at it can still resolve, but the list endpoint hides "
        "it by default."
    ),
)
async def archive_collection(
    id: UUID,
    auth_subject: VectorCollectionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> VectorCollectionSchema:
    collection = await actions.get_or_raise(session, auth_subject, id)
    archived = await actions.archive(session, auth_subject, collection)
    return VectorCollectionSchema.model_validate(archived)


@router.post(
    "/{id}/unarchive",
    summary="Unarchive Vector Collection",
    response_model=VectorCollectionSchema,
    description="Clear ``archived_at``. Idempotent on already-active rows.",
)
async def unarchive_collection(
    id: UUID,
    auth_subject: VectorCollectionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> VectorCollectionSchema:
    collection = await actions.get_or_raise(session, auth_subject, id)
    unarchived = await actions.unarchive(session, auth_subject, collection)
    return VectorCollectionSchema.model_validate(unarchived)


@router.post(
    "/{id}/index",
    summary="Trigger Indexing",
    response_model=IndexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    description=(
        "Dispatch the indexing actor for ``file_id`` into this collection. "
        "Idempotent: re-indexing replaces any prior chunks tagged with the "
        "same source document. The chunk-write happens in a background "
        "worker — the response acknowledges dispatch, not completion."
    ),
)
async def trigger_indexing(
    id: UUID,
    body: IndexRequest,
    auth_subject: VectorCollectionsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> IndexResponse:
    collection = await actions.get_or_raise(session, auth_subject, id)
    try:
        await actions.trigger_index(session, auth_subject, collection, body.file_id)
    except NotPermitted as exc:
        # Archive guard (M5.79) — same 412 mapping the run +
        # eval-run triggers use: resource is gettable but not
        # actionable in its current state.
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc
    return IndexResponse(
        collection_id=collection.id, file_id=body.file_id, dispatched=True
    )
