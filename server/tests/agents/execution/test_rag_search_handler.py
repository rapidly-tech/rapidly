"""Tests for the RAG search node handler.

Validation-only: the query path against a real pgvector index
lives in an integration test alongside the M4.6b indexing
pipeline (which is what produces queryable rows in the first
place).
"""

from __future__ import annotations

import pytest

from rapidly.agents.execution.handlers.rag_search import (
    RagNodeError,
    _embed_query,
    rag_search_handler,
)


@pytest.mark.asyncio
class TestRagSearchValidation:
    async def test_requires_collection_id(self) -> None:
        with pytest.raises(RagNodeError, match="collection_id is required"):
            await rag_search_handler({}, {}, {"query": "hi"})

    async def test_rejects_non_uuid_collection_id(self) -> None:
        with pytest.raises(RagNodeError, match="not a UUID"):
            await rag_search_handler({}, {"collection_id": "abc"}, {"query": "hi"})

    async def test_requires_query(self) -> None:
        # Use a real UUID so we pass the UUID-shape check and land
        # on the query-required check.
        from uuid import uuid4

        with pytest.raises(RagNodeError, match="query is required"):
            await rag_search_handler({}, {"collection_id": str(uuid4())}, {})

    async def test_rejects_empty_query(self) -> None:
        from uuid import uuid4

        with pytest.raises(RagNodeError, match="query is required"):
            await rag_search_handler(
                {}, {"collection_id": str(uuid4())}, {"query": "   "}
            )

    async def test_rejects_k_below_one(self) -> None:
        from uuid import uuid4

        with pytest.raises(RagNodeError, match="k must be"):
            await rag_search_handler(
                {},
                {"collection_id": str(uuid4()), "k": 0},
                {"query": "hi"},
            )


@pytest.mark.asyncio
class TestEmbedQuery:
    async def test_test_provider_returns_deterministic_vector(self) -> None:
        # The test provider produces a fixed vector keyed by dim
        # so the search handler can be unit-tested without an
        # OpenAI / Anthropic / Google round trip.
        vec = await _embed_query(text="anything", model_id="test:4", node_config={})
        assert vec == [0.0, 0.25, 0.5, 0.75]

    async def test_rejects_missing_colon(self) -> None:
        with pytest.raises(RagNodeError, match="must be in 'provider:model'"):
            await _embed_query(text="hi", model_id="just-a-model-name", node_config={})

    async def test_rejects_unsupported_provider(self) -> None:
        with pytest.raises(RagNodeError, match="unsupported embedding provider"):
            await _embed_query(text="hi", model_id="cohere:some-model", node_config={})

    async def test_rejects_non_int_test_suffix(self) -> None:
        with pytest.raises(RagNodeError, match="test embedding model"):
            await _embed_query(text="hi", model_id="test:not-an-int", node_config={})
