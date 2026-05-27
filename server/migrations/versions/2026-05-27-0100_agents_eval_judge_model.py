"""agents: judge_model_id on eval_runs

Adds the column the M4.8d llm_judge strategy needs to know
which model to grade with. Nullable — only the llm_judge
strategy reads it; the comparator raises a clean
LlmJudgeStrategyError if it's missing when needed.

Revision ID: c0b9e2a5d471
Revises: b6d8e57f3a91
Create Date: 2026-05-27 01:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c0b9e2a5d471"
down_revision = "b6d8e57f3a91"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_eval_runs",
        sa.Column("judge_model_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_eval_runs", "judge_model_id")
