"""Pydantic schemas for the VectorCollection API surface."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# Same provider:model shape the embedder dispatch uses. Mirrored
# here so the API can reject bad strings before they make it into
# the DB; the embedder's own dispatch is the final source of
# truth on what providers are supported.
_EMBEDDING_MODEL_PATTERN = r"^[a-z0-9_-]+:[A-Za-z0-9._:/-]+$"


class VectorCollectionCreate(BaseModel):
    """Create payload.

    ``embedding_model`` is immutable after create — changing the
    embedding model invalidates every chunk in the collection
    (the vectors would be from a different geometry). Operators
    who want to switch embedding models should create a new
    collection and re-index.
    """

    workspace_id: UUID
    project_id: UUID | None = None
    name: str = Field(min_length=1, max_length=256)
    embedding_model: str = Field(
        min_length=3,
        max_length=128,
        pattern=_EMBEDDING_MODEL_PATTERN,
        description=(
            "Provider:model identifier consumed by the embedder. "
            "Examples: ``openai:text-embedding-3-small``, ``test:1536``."
        ),
    )
    dimensions: int = Field(
        ge=1,
        le=16000,
        description=(
            "Dimensionality the embedding model produces. Must match "
            "what the chosen model returns; mismatches fail indexing."
        ),
    )


class VectorCollectionUpdate(BaseModel):
    """Update payload. ``embedding_model`` + ``dimensions`` are
    deliberately omitted — they're immutable after create."""

    name: str | None = Field(default=None, min_length=1, max_length=256)
    project_id: UUID | None = None


class VectorCollectionSchema(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID | None
    name: str
    embedding_model: str
    dimensions: int
    created_at: datetime
    modified_at: datetime | None

    model_config = {"from_attributes": True}


class IndexRequest(BaseModel):
    """Trigger an indexing run for ``file_id`` into this collection.

    Idempotent: re-indexing replaces any prior chunks tagged with
    the same ``source_document_id``. See
    ``agents.rag.workers.index_document``.
    """

    file_id: UUID


class IndexResponse(BaseModel):
    """Acknowledgement that the indexing actor was dispatched.

    The actual chunk-write happens in the background worker — the
    caller should poll the collection's chunk count (or a future
    /jobs endpoint) to know when indexing completes.
    """

    collection_id: UUID
    file_id: UUID
    dispatched: bool
