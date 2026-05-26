"""Dramatiq actor that indexes a File into a VectorCollection.

End-to-end flow:
    1. Load the VectorCollection + File rows.
    2. Resolve the workspace's embedding credential via the
       IntegrationCredential store (M4.7c); fall back to
       ``OPENAI_API_KEY`` env if the workspace has no default.
    3. Download the file bytes from S3.
    4. Dispatch the chunker by mime type.
    5. Embed each chunk in batches (via the shared embedder).
    6. Replace any existing chunks for ``(collection_id, file_id)``
       with the new ones — re-indexing is the normal way to update
       a document.

Idempotency:
    The pre-insert delete makes the actor safe to re-dispatch.
    Dramatiq's at-least-once delivery means we need this — without
    it, a retry after a partial insert would leave the collection
    holding duplicate chunks.

Session discipline:
    ``await session.flush()`` only. The actor framework commits at
    task completion; an explicit commit here would force-write
    state ahead of the framework's transaction boundary.

Workspace_id source:
    Derived from ``collection.workspace_id`` after loading the
    collection — no new ``dispatch_task`` parameter needed.
    Keeps the API trigger surface (``POST .../{id}/index``)
    backward-compatible with M4.6c.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import delete, select

from rapidly.agents.rag.chunkers import UnsupportedMimeError, chunk_for_mime
from rapidly.agents.rag.embedder import EmbedderError, embed_batch
from rapidly.models import File, VectorChunk, VectorCollection
from rapidly.worker import AsyncSessionMaker, TaskPriority, actor

_log = structlog.get_logger(__name__)


# Hard cap on chunks per indexing run. A 1 MB plain-text file with
# 1500-char chunks ≈ 700 chunks; bigger sources should be split
# into multiple File rows before indexing. The cap exists to keep
# a single bad upload (a 100 MB minified JSON, say) from monopolising
# the worker pool.
_MAX_CHUNKS_PER_RUN = 2000

# Embedding batch size. OpenAI accepts up to 2048 inputs per call;
# 100 keeps per-batch latency low enough that a retry doesn't lose
# much progress and the actor stays responsive to cancellation.
_EMBED_BATCH_SIZE = 100

# S3 download chunk size — matches file_io handler.
_S3_READ_CHUNK = 64 * 1024


class IndexingError(RuntimeError):
    """Raised on indexer failures the caller should see in the dlq log."""


@actor(actor_name="agents.rag.index_document", priority=TaskPriority.LOW, max_retries=2)
async def index_document(collection_id: UUID, file_id: UUID) -> None:
    """Chunk + embed ``file_id`` into ``collection_id``.

    Replaces any pre-existing chunks tagged with the same
    ``source_document_id`` — call this on every re-index.
    """
    async with AsyncSessionMaker() as session:
        try:
            await _index_document_inner(session, collection_id, file_id)
        except Exception:
            _log.exception(
                "agents.rag.index_document.unhandled",
                collection_id=str(collection_id),
                file_id=str(file_id),
            )
            raise


async def _index_document_inner(
    session: Any,
    collection_id: UUID,
    file_id: UUID,
) -> None:
    coll_stmt = select(VectorCollection).where(VectorCollection.id == collection_id)
    collection = (await session.execute(coll_stmt)).scalar_one_or_none()
    if collection is None:
        raise IndexingError(f"VectorCollection {collection_id} not found")

    file_stmt = select(File).where(File.id == file_id)
    file_row = (await session.execute(file_stmt)).scalar_one_or_none()
    if file_row is None:
        raise IndexingError(f"File {file_id} not found")

    raw = await _download_file_bytes(file_row)

    try:
        chunk_texts = chunk_for_mime(file_row.mime_type, raw)
    except UnsupportedMimeError as exc:
        raise IndexingError(str(exc)) from exc

    if not chunk_texts:
        # Empty source — wipe any prior chunks for this file and exit.
        await session.execute(
            delete(VectorChunk).where(
                VectorChunk.collection_id == collection_id,
                VectorChunk.source_document_id == file_id,
            )
        )
        await session.flush()
        return

    if len(chunk_texts) > _MAX_CHUNKS_PER_RUN:
        raise IndexingError(
            f"file {file_id} produced {len(chunk_texts)} chunks; "
            f"max per run is {_MAX_CHUNKS_PER_RUN}"
        )

    # Hand the embedder the session + workspace_id so it can read
    # the workspace's default credential from IntegrationCredential
    # (M4.7c). Falls back to OPENAI_API_KEY env when no credential
    # is configured — the embedder's own resolver owns that path.
    embed_options: dict[str, Any] = {
        "session": session,
        "workspace_id": collection.workspace_id,
    }
    embeddings: list[list[float]] = []
    for batch_start in range(0, len(chunk_texts), _EMBED_BATCH_SIZE):
        batch = chunk_texts[batch_start : batch_start + _EMBED_BATCH_SIZE]
        try:
            vecs = await embed_batch(
                batch,
                model_id=collection.embedding_model,
                options=embed_options,
            )
        except EmbedderError as exc:
            raise IndexingError(str(exc)) from exc
        for vec in vecs:
            if len(vec) != collection.dimensions:
                raise IndexingError(
                    f"embedded vector has {len(vec)} dims; "
                    f"collection expects {collection.dimensions}"
                )
        embeddings.extend(vecs)

    await session.execute(
        delete(VectorChunk).where(
            VectorChunk.collection_id == collection_id,
            VectorChunk.source_document_id == file_id,
        )
    )

    base_metadata = {
        "file_name": file_row.name,
        "file_mime_type": file_row.mime_type,
    }
    for idx, (text, vec) in enumerate(zip(chunk_texts, embeddings, strict=True)):
        session.add(
            VectorChunk(
                collection_id=collection_id,
                source_document_id=file_id,
                chunk_index=idx,
                text=text,
                chunk_metadata=base_metadata,
                embedding=vec,
            )
        )
    await session.flush()


async def _download_file_bytes(file_row: File) -> bytes:
    """Pull the raw bytes for ``file_row`` from its S3 backend.

    Mirrors the pattern in
    ``agents/execution/handlers/file_io.py`` so the indexer doesn't
    need a shared dependency just for one helper. boto3's
    ``get_object`` is sync so we route it through ``to_thread``.
    """
    # Inline imports keep boto3 + catalog out of the module's
    # import tree until an indexing job actually runs.
    from rapidly.catalog.file.s3 import S3_SERVICES

    def _download_sync() -> bytes:
        s3 = S3_SERVICES[file_row.service]
        obj = s3.get_object_or_raise(file_row.path)
        body = obj.get("Body")
        if body is None:
            raise IndexingError(f"S3 GetObject returned no Body for {file_row.path}")
        buf = bytearray()
        while True:
            chunk = body.read(_S3_READ_CHUNK)
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    return await asyncio.to_thread(_download_sync)
