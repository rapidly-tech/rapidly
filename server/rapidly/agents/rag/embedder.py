"""Embedder — turn a batch of texts into vectors via a provider's API.

This module is the single source of truth for embedding dispatch.
Both the rag_search handler (one text at a time) and the indexing
worker (a batch per chunk run) call into here.

Provider format: ``"<provider>:<model>"`` (e.g.
``"openai:text-embedding-3-small"``). Supported providers:

- ``openai`` — OpenAI hosted embeddings.
- ``ollama`` — same OpenAI client shape, different ``base_url``.
- ``test`` — deterministic vector fixture for unit tests. Suffix
  is the dimension (``"test:4"`` → 4-dim vectors).

API keys + base URLs flow through ``options`` so the search handler
(reads from node_config) and the indexer worker (reads from
collection config + env) can both supply them. The dict shape keeps
the surface narrow without forcing a Pydantic model on every caller.
"""

from __future__ import annotations

import os
from typing import Any


class EmbedderError(RuntimeError):
    """Surfaces to the calling handler / worker's failure path."""


_PROVIDERS_USING_OPENAI_CLIENT = {"openai", "ollama"}


async def embed_batch(
    texts: list[str],
    *,
    model_id: str,
    options: dict[str, Any] | None = None,
) -> list[list[float]]:
    """Embed a batch of texts. Returns one vector per input text.

    The batch order matches the input order — callers can ``zip``
    the result with their source chunks without re-keying.
    """
    if not texts:
        return []
    if ":" not in model_id:
        raise EmbedderError(
            f"embedding_model {model_id!r} must be in 'provider:model' form"
        )
    provider, model = model_id.split(":", 1)
    opts = options or {}

    if provider == "test":
        try:
            dim = int(model)
        except ValueError as exc:
            raise EmbedderError(
                f"test embedding model suffix must be int, got {model!r}"
            ) from exc
        return [[i / dim for i in range(dim)] for _ in texts]

    if provider in _PROVIDERS_USING_OPENAI_CLIENT:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover — openai is in deps
            raise EmbedderError("openai package not installed") from exc

        api_key = opts.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = opts.get("base_url") or None
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        try:
            resp = await client.embeddings.create(model=model, input=texts)
        except Exception as exc:
            raise EmbedderError(f"embedding call failed: {exc}") from exc
        # OpenAI returns embeddings in the same order as ``input``.
        return [list(d.embedding) for d in resp.data]

    raise EmbedderError(
        f"unsupported embedding provider {provider!r} "
        "(v1 supports openai / ollama / test)"
    )


async def embed_one(
    text: str,
    *,
    model_id: str,
    options: dict[str, Any] | None = None,
) -> list[float]:
    """Single-text convenience wrapper around ``embed_batch``."""
    out = await embed_batch([text], model_id=model_id, options=options)
    return out[0]
