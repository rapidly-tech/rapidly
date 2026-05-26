"""agents: eval_runs + eval_run_cases

Adds the M4.8b eval runner's data tables. The runner actor
creates one EvalRun per ``trigger_eval`` API call + one
EvalRunCase per dataset case (with input/expected snapshots
so deleting the source case doesn't orphan historical evals).

Revision ID: b6d8e57f3a91
Revises: a2c4e91f2d63
Create Date: 2026-05-27 00:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b6d8e57f3a91"
down_revision = "a2c4e91f2d63"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_eval_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("assertion_strategy", sa.String(length=32), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pass_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["agent_datasets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_version_id"],
            ["workflow_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_eval_runs_workspace_id"),
        "agent_eval_runs",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_agent_eval_runs_dataset_id"),
        "agent_eval_runs",
        ["dataset_id"],
    )
    op.create_index(
        op.f("ix_agent_eval_runs_workflow_version_id"),
        "agent_eval_runs",
        ["workflow_version_id"],
    )

    op.create_table(
        "agent_eval_run_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("eval_run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("case_name", sa.Text(), nullable=False),
        sa.Column("case_input_data", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "case_expected_output",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column("actual_output", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["eval_run_id"], ["agent_eval_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["agent_dataset_cases.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_eval_run_cases_eval_run_id"),
        "agent_eval_run_cases",
        ["eval_run_id"],
    )
    op.create_index(
        op.f("ix_agent_eval_run_cases_case_id"),
        "agent_eval_run_cases",
        ["case_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_eval_run_cases_case_id"),
        table_name="agent_eval_run_cases",
    )
    op.drop_index(
        op.f("ix_agent_eval_run_cases_eval_run_id"),
        table_name="agent_eval_run_cases",
    )
    op.drop_table("agent_eval_run_cases")
    op.drop_index(
        op.f("ix_agent_eval_runs_workflow_version_id"),
        table_name="agent_eval_runs",
    )
    op.drop_index(op.f("ix_agent_eval_runs_dataset_id"), table_name="agent_eval_runs")
    op.drop_index(
        op.f("ix_agent_eval_runs_workspace_id"),
        table_name="agent_eval_runs",
    )
    op.drop_table("agent_eval_runs")
