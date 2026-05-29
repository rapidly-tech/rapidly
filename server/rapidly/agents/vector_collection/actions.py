"""VectorCollection lifecycle: list, get, create, update, delete, index.

The indexer-trigger entry point dispatches the
``agents.rag.index_document`` actor; the chunking + embedding +
upsert happens in the worker — see ``agents.rag.workers``.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from rapidly.agents.vector_collection.queries import VectorCollectionRepository
from rapidly.agents.vector_collection.types import (
    VectorCollectionCreate,
    VectorCollectionUpdate,
)
from rapidly.catalog.file.queries import FileRepository
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.core.utils import now_utc
from rapidly.errors import NotPermitted, ResourceNotFound
from rapidly.identity.auth.models import (
    AuthPrincipal,
    User,
    Workspace,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import VectorCollection, WorkspaceMembership
from rapidly.postgres import AsyncReadSession, AsyncSession
from rapidly.worker import dispatch_task


async def get(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> VectorCollection | None:
    repo = VectorCollectionRepository.from_session(session)
    stmt = repo.get_readable_statement(auth_subject).where(VectorCollection.id == id)
    return await repo.get_one_or_none(stmt)


async def get_or_raise(
    session: AsyncSession | AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> VectorCollection:
    collection = await get(session, auth_subject, id)
    if collection is None:
        raise ResourceNotFound("VectorCollection not found.")
    return collection


async def list_collections(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    name: str | None = None,
    is_archived: bool | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[VectorCollection], int]:
    repo = VectorCollectionRepository.from_session(session)
    statement = repo.get_readable_statement(auth_subject)
    if workspace_id is not None:
        # Mirrors the workflow/dataset list contract (M5.41, M5.42).
        statement = statement.where(VectorCollection.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(VectorCollection.project_id == project_id)
    if is_archived is True:
        # Tri-state archive filter, same shape as workflows /
        # datasets (M5.65 / M5.68).
        statement = statement.where(VectorCollection.archived_at.is_not(None))
    elif is_archived is False:
        statement = statement.where(VectorCollection.archived_at.is_(None))
    if name is not None and name.strip():
        # Same SQL-wildcard-safe escape as the workflows/datasets/
        # credentials name filter (M5.25, M5.39).
        escaped = (
            name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        statement = statement.where(
            VectorCollection.name.ilike(f"%{escaped}%", escape="\\")
        )
    return await paginate(session, statement, pagination=pagination)


async def create(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    data: VectorCollectionCreate,
) -> VectorCollection:
    await _assert_workspace_writable(session, auth_subject, data.workspace_id)
    repo = VectorCollectionRepository.from_session(session)
    record = VectorCollection(
        workspace_id=data.workspace_id,
        project_id=data.project_id,
        name=data.name,
        embedding_model=data.embedding_model,
        dimensions=data.dimensions,
    )
    return await repo.create(record, flush=True)


async def update(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    collection: VectorCollection,
    data: VectorCollectionUpdate,
) -> VectorCollection:
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return collection
    repo = VectorCollectionRepository.from_session(session)
    return await repo.update(collection, update_dict=update_dict)


async def delete(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    collection: VectorCollection,
) -> None:
    repo = VectorCollectionRepository.from_session(session)
    await repo.soft_delete(collection)


async def archive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    collection: VectorCollection,
) -> VectorCollection:
    """Stamp ``archived_at = now()`` if not already archived.

    Idempotent — mirrors the workflow + dataset archive shape
    (M5.65 / M5.68).
    """
    if collection.archived_at is not None:
        return collection
    repo = VectorCollectionRepository.from_session(session)
    return await repo.update(
        collection, update_dict={"archived_at": now_utc()}, flush=True
    )


async def unarchive(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    collection: VectorCollection,
) -> VectorCollection:
    """Clear ``archived_at``. Idempotent on already-active rows."""
    if collection.archived_at is None:
        return collection
    repo = VectorCollectionRepository.from_session(session)
    return await repo.update(collection, update_dict={"archived_at": None}, flush=True)


async def trigger_index(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    collection: VectorCollection,
    file_id: UUID,
) -> None:
    """Dispatch the indexing actor for ``file_id`` into ``collection``.

    The file must be in the same workspace as the collection — we
    won't index a file the caller's workspace doesn't own, even
    if the caller has read on both. The check happens here (not
    just at the worker) so the API returns 404 immediately rather
    than the actor failing asynchronously after the response.
    """
    if collection.archived_at is not None:
        # Symmetric with the workflow + dataset archive guards
        # (M5.78): an archived collection is retired by user
        # intent, so indexing into it would contradict the
        # user-facing "active only" default on the list and
        # let stale data leak into a corpus the operator
        # deliberately mothballed. Unarchive before indexing.
        raise NotPermitted(
            "Vector collection is archived. Unarchive it before indexing."
        )

    file_repo = FileRepository.from_session(session)
    file_stmt = file_repo.get_base_statement().where(
        file_repo.model.id == file_id,
        file_repo.model.workspace_id == collection.workspace_id,
        file_repo.model.deleted_at.is_(None),
    )
    file_row = await file_repo.get_one_or_none(file_stmt)
    if file_row is None:
        raise ResourceNotFound("File not found in this workspace.")

    dispatch_task(
        "agents.rag.index_document",
        collection_id=collection.id,
        file_id=file_id,
    )


async def _assert_workspace_writable(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    workspace_id: UUID,
) -> None:
    """Confirm the caller can create resources in ``workspace_id``.

    User principal: needs an active membership.
    Workspace principal: the workspace must be the caller's own.
    """
    if is_user_principal(auth_subject):
        stmt = (
            select(WorkspaceMembership.user_id)
            .where(
                WorkspaceMembership.user_id == auth_subject.subject.id,
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.deleted_at.is_(None),
            )
            .limit(1)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            raise ResourceNotFound("Workspace not found.")
        return
    if is_workspace_principal(auth_subject):
        if auth_subject.subject.id != workspace_id:
            raise ResourceNotFound("Workspace not found.")
        return
    raise ResourceNotFound("Workspace not found.")
