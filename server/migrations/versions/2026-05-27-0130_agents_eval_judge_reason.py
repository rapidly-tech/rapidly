"""agents: judge_reason on eval_run_cases

Persists the grader LLM's narrative pass/fail explanation
(M4.8e). The comparator already produces it for the
``llm_judge`` strategy — we were just throwing it away.

Revision ID: d4f1a8c7e592
Revises: c0b9e2a5d471
Create Date: 2026-05-27 01:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4f1a8c7e592"
down_revision = "c0b9e2a5d471"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_eval_run_cases",
        sa.Column("judge_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_eval_run_cases", "judge_reason")
