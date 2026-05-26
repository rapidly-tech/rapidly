"""agents: llm_usage table

Adds per-call LLM usage tracking. Written by the LLM +
structured-output handlers after each successful provider call;
queried by per-credential + per-workspace billing rollups (M4.7d).

Revision ID: e1f7a23b4d50
Revises: c8c2f17d3a91
Create Date: 2026-05-26 23:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e1f7a23b4d50"
down_revision = "c8c2f17d3a91"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("node_run_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["integration_credentials.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["node_run_id"], ["agent_node_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_llm_usage_workspace_id"), "llm_usage", ["workspace_id"])
    op.create_index(op.f("ix_llm_usage_credential_id"), "llm_usage", ["credential_id"])
    op.create_index(op.f("ix_llm_usage_run_id"), "llm_usage", ["run_id"])
    op.create_index(op.f("ix_llm_usage_provider"), "llm_usage", ["provider"])
    op.create_index(op.f("ix_llm_usage_occurred_at"), "llm_usage", ["occurred_at"])
    # Composite index for the common rollup query:
    # "tokens spent by ws_X in the last 24h, grouped by provider".
    op.create_index(
        "ix_llm_usage_workspace_occurred",
        "llm_usage",
        ["workspace_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_workspace_occurred", table_name="llm_usage")
    op.drop_index(op.f("ix_llm_usage_occurred_at"), table_name="llm_usage")
    op.drop_index(op.f("ix_llm_usage_provider"), table_name="llm_usage")
    op.drop_index(op.f("ix_llm_usage_run_id"), table_name="llm_usage")
    op.drop_index(op.f("ix_llm_usage_credential_id"), table_name="llm_usage")
    op.drop_index(op.f("ix_llm_usage_workspace_id"), table_name="llm_usage")
    op.drop_table("llm_usage")
