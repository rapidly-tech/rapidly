"""add agent_node_runs table

Implements M4.1d of M4_EXECUTION.md. Closes the M4.1 scaffold by
adding the per-step execution record. The execution engine itself
ships in M4.2.

Revision ID: 9ed2e6b1453d
Revises: dca26501d311
Create Date: 2026-05-26 20:34:37.149907
"""

import sqlalchemy as sa
from alembic import op

# Rapidly Custom Imports
from rapidly.core.extensions.sqlalchemy import StringEnum
from rapidly.models.agent_node_run import NodeRunStatus

# revision identifiers, used by Alembic.
revision = "9ed2e6b1453d"
down_revision = "dca26501d311"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_node_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column(
            "status", StringEnum(NodeRunStatus, length=16), nullable=False
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("input_data", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("output_data", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("parent_node_run_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_node_run_id"], ["agent_node_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_node_runs_run_id"), "agent_node_runs", ["run_id"]
    )
    op.create_index(
        op.f("ix_agent_node_runs_node_id"), "agent_node_runs", ["node_id"]
    )
    op.create_index(
        op.f("ix_agent_node_runs_parent_node_run_id"),
        "agent_node_runs",
        ["parent_node_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_node_runs_parent_node_run_id"),
        table_name="agent_node_runs",
    )
    op.drop_index(
        op.f("ix_agent_node_runs_node_id"), table_name="agent_node_runs"
    )
    op.drop_index(
        op.f("ix_agent_node_runs_run_id"), table_name="agent_node_runs"
    )
    op.drop_table("agent_node_runs")
