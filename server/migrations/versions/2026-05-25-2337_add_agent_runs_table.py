"""add agent_runs table

Implements M4.1c of M4_EXECUTION.md. Creates the ``agent_runs``
table (immutable execution records) + its enums. NodeRun ships in
M4.1d alongside its own submodule.

Revision ID: dca26501d311
Revises: 21aa9b69f43b
Create Date: 2026-05-25 23:37:09.519449
"""

import sqlalchemy as sa
from alembic import op

# Rapidly Custom Imports
from rapidly.core.extensions.sqlalchemy import StringEnum
from rapidly.models.agent_run import RunStatus, TriggeredByKind

# revision identifiers, used by Alembic.
revision = "dca26501d311"
down_revision = "21aa9b69f43b"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "triggered_by_kind",
            StringEnum(TriggeredByKind, length=16),
            nullable=False,
        ),
        sa.Column("triggered_by_id", sa.Uuid(), nullable=True),
        sa.Column("status", StringEnum(RunStatus, length=16), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("input_data", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("output_data", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_version_id"],
            ["workflow_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_runs_workflow_version_id"),
        "agent_runs",
        ["workflow_version_id"],
    )
    op.create_index(
        op.f("ix_agent_runs_triggered_by_id"),
        "agent_runs",
        ["triggered_by_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_runs_triggered_by_id"), table_name="agent_runs"
    )
    op.drop_index(
        op.f("ix_agent_runs_workflow_version_id"), table_name="agent_runs"
    )
    op.drop_table("agent_runs")
