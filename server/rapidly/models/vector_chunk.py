"""A single embedded chunk within a VectorCollection.

The indexing pipeline chunks a source document, embeds each chunk
with the collection's ``embedding_model``, and inserts one row
per chunk. The vector dimension is checked against the parent
collection's ``dimensions`` field at the application layer —
mismatched dims fail at the indexer / search-handler boundary,
not in the DB.

``source_document_id`` is nullable so raw-text inserts (no
source file) are valid too.

Why ``Vector()`` (variable-dim) not ``Vector(N)``:
    A workspace running both an OpenAI 1536-dim collection and a
    voyage-3 1024-dim collection can't coexist in a fixed-dim
    column. The trade-off is that HNSW indexes only work on
    fixed-dim columns — so for v1 we use linear scan + the
    ``<=>`` cosine-distance operator. An ANN index can be added
    later via per-dimension shards or a single-dim deployment.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .file import File
    from .vector_collection import VectorCollection


class VectorChunk(BaseEntity):
    """A single embedded chunk within a VectorCollection."""

    __tablename__ = "vector_chunks"

    collection_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("vector_collections.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    source_document_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("files.id", ondelete="set null"),
        nullable=True,
        index=True,
    )
    # Per-document ordinal — order of chunks within a single source.
    # Useful for "show me the context around this hit" queries.
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Open-ended metadata — page number, heading, source filename.
    # Returned alongside hits so the UI can render "Found in
    # Section 4.2 of arch.pdf at page 17".
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    # Variable-dim vector — the per-row dim is whatever the
    # collection's embedding_model produces. The app layer
    # rejects rows where len(vec) != collection.dimensions.
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)

    @declared_attr
    def collection(cls) -> Mapped["VectorCollection"]:
        return relationship("VectorCollection", lazy="raise")

    @declared_attr
    def source_document(cls) -> Mapped["File | None"]:
        return relationship("File", lazy="raise")
