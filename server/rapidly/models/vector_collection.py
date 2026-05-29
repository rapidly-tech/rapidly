"""A named collection of vector chunks for RAG search.

A VectorCollection groups chunks that were embedded with the same
model + chunked from the same source-document set. RAG-search node
queries are always scoped to a collection (you don't search "all
chunks across the workspace" — you point at a specific corpus).

``embedding_model`` + ``dimensions`` are set at create time and
immutable thereafter. Changing the embedding model means
re-embedding every chunk, which is a re-index, not an update.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project import Project
    from .workspace import Workspace


class VectorCollection(BaseEntity):
    """A vector store collection scoped to a workspace + optional project.

    Soft-delete via ``BaseEntity.deleted_at`` — archived collections
    stay queryable for audit + can be undeleted; chunks cascade-
    delete via the FK.
    """

    __tablename__ = "vector_collections"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    # Embedding model identifier — provider:name, e.g.
    # "openai:text-embedding-3-small". Stored as a free-form string
    # so a workflow author can target Anthropic / Cohere / Ollama
    # embeddings without a schema migration.
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    # Vector dimension — set by the embedding model + immutable.
    # The pgvector ``Vector(dim)`` column on VectorChunk references
    # this number; mismatched dimensions raise at insert time.
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)

    # Archive (separate from soft-delete). Mirrors workflows
    # (M5.65) + datasets (M5.68): operators stash a collection
    # they're no longer indexing into without losing the chunks
    # or breaking RAG-search references that pointed at it.
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    @declared_attr
    def project(cls) -> Mapped["Project | None"]:
        return relationship("Project", lazy="raise")
