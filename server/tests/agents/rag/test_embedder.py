"""Tests for the shared RAG embedder dispatch."""

from __future__ import annotations

import pytest

from rapidly.agents.rag.embedder import EmbedderError, embed_batch, embed_one


@pytest.mark.asyncio
class TestEmbedBatch:
    async def test_empty_list_returns_empty(self) -> None:
        assert await embed_batch([], model_id="test:4") == []

    async def test_test_provider_returns_deterministic_vectors(self) -> None:
        # Same fixture as the rag_search _embed_query test —
        # the deterministic shape lets us assert equality on
        # batched results without juggling tolerance.
        out = await embed_batch(["a", "b"], model_id="test:4")
        assert out == [[0.0, 0.25, 0.5, 0.75], [0.0, 0.25, 0.5, 0.75]]

    async def test_rejects_missing_colon(self) -> None:
        with pytest.raises(EmbedderError, match="must be in 'provider:model'"):
            await embed_batch(["a"], model_id="just-a-model-name")

    async def test_rejects_unsupported_provider(self) -> None:
        with pytest.raises(EmbedderError, match="unsupported embedding provider"):
            await embed_batch(["a"], model_id="cohere:some-model")

    async def test_rejects_non_int_test_suffix(self) -> None:
        with pytest.raises(EmbedderError, match="test embedding model"):
            await embed_batch(["a"], model_id="test:not-an-int")


@pytest.mark.asyncio
class TestEmbedOne:
    async def test_returns_single_vector(self) -> None:
        out = await embed_one("hi", model_id="test:3")
        assert out == [0.0, 1 / 3, 2 / 3]
