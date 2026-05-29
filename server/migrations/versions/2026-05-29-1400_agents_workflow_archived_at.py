"""agents: archived_at column on workflows

Adds an ``archived_at`` timestamp + index so operators can archive
workflows without soft-deleting them. Archived rows stay queryable
(past runs need their parent workflow's name + workspace) but the
list endpoint hides them by default — separate axis from
``deleted_at``.

Revision ID: f9d2c81a5e34
Revises: e7a2c43d8b91
Create Date: 2026-05-29 14:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f9d2c81a5e34"
down_revision = "e7a2c43d8b91"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_workflows_archived_at"),
        "workflows",
        ["archived_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_workflows_archived_at"), table_name="workflows")
    op.drop_column("workflows", "archived_at")
