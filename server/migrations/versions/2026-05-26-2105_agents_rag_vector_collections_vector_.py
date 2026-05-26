"""agents rag: vector_collections + vector_chunks + extension

Implements M4.6 of M4_EXECUTION.md (RAG scaffold half). Creates
the vector_collections + vector_chunks tables and activates the
pgvector vector extension.

Indexing pipeline (the Dramatiq actor that chunks + embeds source
documents) lands in M4.6b. This migration ships the schema so the
RAG search node can query against rows populated by hand or by
the future indexer.

The ``embedding`` column is variable-dim (Vector() with no
declared size) so a single workspace can host collections with
different embedding-model dimensions. The trade-off: HNSW indexes
require a fixed dim, so v1 uses linear scan via the ``<=>``
cosine-distance operator. A per-dim ANN index can ship later.

Postgres image: the dev compose's postgres:16-bookworm does NOT
include the vector extension. Operators need to swap the image
to pgvector/pgvector:pg16 (or install the extension by hand)
before this migration applies; CREATE EXTENSION vector will
otherwise fail with "extension is not available".

Revision ID: 0ea0d9668ef2
Revises: 9ed2e6b1453d
Create Date: 2026-05-26 21:05:18.572889
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# Rapidly Custom Imports

# revision identifiers, used by Alembic.
revision = "0ea0d9668ef2"
down_revision = "9ed2e6b1453d"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "vector_collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vector_collections_workspace_id"),
        "vector_collections",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_vector_collections_project_id"),
        "vector_collections",
        ["project_id"],
    )

    op.create_table(
        "vector_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "chunk_metadata",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column("embedding", Vector(), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["vector_collections.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["files.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vector_chunks_collection_id"),
        "vector_chunks",
        ["collection_id"],
    )
    op.create_index(
        op.f("ix_vector_chunks_source_document_id"),
        "vector_chunks",
        ["source_document_id"],
    )
    # No HNSW index for v1: HNSW requires a fixed-dim column and
    # ``embedding`` is variable-dim. Linear scan over a workspace's
    # collection (typically a few thousand chunks) is fine for v1
    # scale; a follow-up can shard per dimension if a workspace
    # grows past 100K chunks in one collection.


def downgrade() -> None:
    op.drop_index(
        op.f("ix_vector_chunks_source_document_id"),
        table_name="vector_chunks",
    )
    op.drop_index(
        op.f("ix_vector_chunks_collection_id"),
        table_name="vector_chunks",
    )
    op.drop_table("vector_chunks")
    op.drop_index(
        op.f("ix_vector_collections_project_id"),
        table_name="vector_collections",
    )
    op.drop_index(
        op.f("ix_vector_collections_workspace_id"),
        table_name="vector_collections",
    )
    op.drop_table("vector_collections")
    # Don't drop the extension itself — other features may rely on
    # it (or may rely on it in the future). Dropping is operator-
    # initiated, not migration-driven.
