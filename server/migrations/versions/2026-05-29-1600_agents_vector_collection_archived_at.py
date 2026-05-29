"""agents: archived_at column on vector_collections

Mirrors the workflow + dataset archive shape (M5.65 + M5.68) for
vector collections. Operators stash collections they're no
longer indexing into without losing the chunks or breaking
RAG-search references that pointed at them.

Revision ID: a5b8e92d1f47
Revises: c6e84f3a7b21
Create Date: 2026-05-29 16:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a5b8e92d1f47"
down_revision = "c6e84f3a7b21"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vector_collections",
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_vector_collections_archived_at"),
        "vector_collections",
        ["archived_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_vector_collections_archived_at"),
        table_name="vector_collections",
    )
    op.drop_column("vector_collections", "archived_at")
