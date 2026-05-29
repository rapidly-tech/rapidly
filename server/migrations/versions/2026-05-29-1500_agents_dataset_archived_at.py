"""agents: archived_at column on agent_datasets

Mirrors the workflow archive shape (M5.65 / f9d2c81a5e34) for
the dataset table. Operators stash datasets without losing them
— past eval-runs still resolve their parent by id, but the list
endpoint hides archived rows by default.

Revision ID: c6e84f3a7b21
Revises: f9d2c81a5e34
Create Date: 2026-05-29 15:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c6e84f3a7b21"
down_revision = "f9d2c81a5e34"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_datasets",
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_agent_datasets_archived_at"),
        "agent_datasets",
        ["archived_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_datasets_archived_at"), table_name="agent_datasets")
    op.drop_column("agent_datasets", "archived_at")
