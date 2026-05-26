"""RAG search node — top-K cosine-similarity lookup against a VectorCollection.

This handler ships the **query side** of M4.6. The indexing
pipeline that produces VectorChunk rows lives in M4.6b — until
then a workflow author can populate chunks via direct DB inserts
or a follow-up indexer-worker.

The query path takes a text input, embeds it with the collection's
configured model, and runs the pgvector cosine-distance query for
the top-K nearest chunks. Returns text + score + metadata per hit.

Embedding the query is unavoidable here — there's no other way to
turn the engineer's natural-language question into a vector. We
reuse pydantic-ai's openai provider for the embedding call by
default; per-collection embedding-model strings let workflows
target Cohere / Ollama / etc. via the same dispatch shape.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from rapidly.agents.rag.embedder import EmbedderError, embed_one
from rapidly.models import VectorChunk, VectorCollection
from rapidly.worker import AsyncSessionMaker


class RagNodeError(RuntimeError):
    """Surfaces to the engine's per-node failure path."""


_DEFAULT_K = 5
_MAX_K = 50


async def rag_search_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """Search a VectorCollection for the top-K chunks most similar
    to the query.

    ``node_config`` fields:
        collection_id: UUID   required
        k: int                optional, default 5, capped at 50

    Query text comes from ``input_data["query"]`` — the editor
    wires this from a previous node's output (e.g. an LLM that
    extracted an intent from a user message).
    """
    raw_collection = node_config.get("collection_id")
    if not isinstance(raw_collection, str):
        raise RagNodeError("collection_id is required")
    try:
        collection_id = UUID(raw_collection)
    except (TypeError, ValueError) as exc:
        raise RagNodeError(f"collection_id is not a UUID: {raw_collection!r}") from exc

    query = input_data.get("query")
    if not isinstance(query, str) or not query.strip():
        raise RagNodeError(
            "input_data.query is required and must be a non-empty string"
        )

    k = int(node_config.get("k", _DEFAULT_K))
    if k < 1:
        raise RagNodeError("k must be >= 1")
    if k > _MAX_K:
        k = _MAX_K

    async with AsyncSessionMaker() as session:
        coll_stmt = select(VectorCollection).where(VectorCollection.id == collection_id)
        collection = (await session.execute(coll_stmt)).scalar_one_or_none()
        if collection is None:
            raise RagNodeError(f"VectorCollection {collection_id} not found")

        options = {
            "api_key": node_config.get("api_key"),
            "base_url": node_config.get("base_url"),
        }
        try:
            query_vec = await embed_one(
                query,
                model_id=collection.embedding_model,
                options=options,
            )
        except EmbedderError as exc:
            raise RagNodeError(str(exc)) from exc
        if len(query_vec) != collection.dimensions:
            raise RagNodeError(
                f"embedded query has {len(query_vec)} dims; "
                f"collection expects {collection.dimensions}"
            )

        # pgvector cosine distance: ``<=>``. We select the
        # distance alongside the row so the response can include
        # a relevance score (1 - distance gives the cosine
        # similarity in [0, 1]).
        stmt = (
            select(
                VectorChunk,
                VectorChunk.embedding.cosine_distance(query_vec).label("dist"),
            )
            .where(VectorChunk.collection_id == collection_id)
            .order_by("dist")
            .limit(k)
        )
        rows = (await session.execute(stmt)).all()

    return {
        "results": [
            {
                "id": str(chunk.id),
                "text": chunk.text,
                "score": float(1.0 - float(distance)),
                "metadata": chunk.chunk_metadata,
                "source_document_id": (
                    str(chunk.source_document_id) if chunk.source_document_id else None
                ),
            }
            for chunk, distance in rows
        ],
    }


async def _embed_query(
    *,
    text: str,
    model_id: str,
    node_config: dict[str, Any],
) -> list[float]:
    """Compat shim — routes through the shared embedder module.

    Kept as a private wrapper so existing tests
    (``tests/agents/execution/test_rag_search_handler.py``) that
    import ``_embed_query`` directly still pass. The real
    implementation lives in ``rapidly.agents.rag.embedder``.
    """
    options = {
        "api_key": node_config.get("api_key"),
        "base_url": node_config.get("base_url"),
    }
    try:
        return await embed_one(text, model_id=model_id, options=options)
    except EmbedderError as exc:
        raise RagNodeError(str(exc)) from exc
