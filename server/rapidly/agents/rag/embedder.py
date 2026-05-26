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

Credential resolution order (M4.7b):
    1. ``options["api_key"]`` if explicitly passed (caller-owned)
    2. ``IntegrationCredential`` for ``(workspace_id, provider)``
       when ``options["session"]`` + ``options["workspace_id"]``
       are present
    3. ``OPENAI_API_KEY`` from process env — fallback for the
       indexer worker until M4.7c finishes per-job context plumbing

The IntegrationCredential lookup uses the default credential for
the workspace + provider unless ``options["credential_id"]`` is
set to override. base_url from the credential overrides the
canonical hostname; the caller's explicit ``options["base_url"]``
still wins over both.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID


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

        api_key, resolved_base_url = await _resolve_credential(
            provider=provider, opts=opts
        )
        # Explicit caller base_url overrides credential base_url
        # (test setups want to point at a local stub regardless of
        # what's configured per-workspace).
        base_url = opts.get("base_url") or resolved_base_url
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


async def _resolve_credential(
    *, provider: str, opts: dict[str, Any]
) -> tuple[str | None, str | None]:
    """Pick the API key + base URL for ``provider``.

    Priority order:
        1. ``opts["api_key"]`` if the caller explicitly passed one.
        2. ``IntegrationCredential`` for the workspace + provider
           if ``opts["session"]`` + ``opts["workspace_id"]`` are
           supplied (handlers running inside the engine).
        3. ``OPENAI_API_KEY`` env var — fallback for the indexer
           worker until M4.7c plumbs workspace_id through.

    Returns ``(api_key_or_None, base_url_or_None)``.
    """
    explicit_key = opts.get("api_key")
    if explicit_key:
        return explicit_key, None

    session = opts.get("session")
    workspace_id = opts.get("workspace_id")
    if session is not None and workspace_id is not None:
        # Inline import keeps the embedder importable even when
        # the integration_credential submodule isn't wired (e.g.,
        # in narrow unit tests).
        from rapidly.agents.integration_credential.queries import (
            resolve_for_workspace,
        )

        ws_uuid = (
            workspace_id if isinstance(workspace_id, UUID) else UUID(str(workspace_id))
        )
        credential_id = opts.get("credential_id")
        cred_uuid: UUID | None = None
        if credential_id is not None:
            cred_uuid = (
                credential_id
                if isinstance(credential_id, UUID)
                else UUID(str(credential_id))
            )
        result = await resolve_for_workspace(
            session,
            workspace_id=ws_uuid,
            provider=provider,
            credential_id=cred_uuid,
        )
        if result is not None:
            return result

    # Env fallback. Indexer worker hits this path; once M4.7c
    # threads workspace context through the indexer, the env
    # fallback becomes a last-resort dev escape hatch.
    return os.environ.get("OPENAI_API_KEY"), None
