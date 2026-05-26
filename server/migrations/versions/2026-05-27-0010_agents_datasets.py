"""agents: dataset + dataset_case tables

Adds the Dataset + DatasetCase models that the eval runner
(M4.8b) consumes. CRUD-only in M4.8a; runner is a separate PR.

Revision ID: a2c4e91f2d63
Revises: f9d3e54b8e21
Create Date: 2026-05-27 00:10:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a2c4e91f2d63"
down_revision = "f9d3e54b8e21"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_datasets_workspace_id"),
        "agent_datasets",
        ["workspace_id"],
    )

    op.create_table(
        "agent_dataset_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("input_data", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("expected_output", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["agent_datasets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_dataset_cases_dataset_id"),
        "agent_dataset_cases",
        ["dataset_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_dataset_cases_dataset_id"),
        table_name="agent_dataset_cases",
    )
    op.drop_table("agent_dataset_cases")
    op.drop_index(
        op.f("ix_agent_datasets_workspace_id"),
        table_name="agent_datasets",
    )
    op.drop_table("agent_datasets")
