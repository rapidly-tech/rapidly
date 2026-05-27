"""agents: budget_alert columns on integration_credentials

Adds the M4.7h alerting state on each credential:
``budget_alert_threshold_percent`` (operator-configured threshold,
e.g., 80 for 80%) and ``budget_alert_triggered_at`` (set by the
LLM handler the first time MTD crosses the threshold each month).

The alerts endpoint compares ``budget_alert_triggered_at``'s
calendar month to the current month; matching = active alert.

Revision ID: e7a2c43d8b91
Revises: d4f1a8c7e592
Create Date: 2026-05-27 02:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e7a2c43d8b91"
down_revision = "d4f1a8c7e592"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integration_credentials",
        sa.Column(
            "budget_alert_threshold_percent", sa.Integer(), nullable=True
        ),
    )
    op.add_column(
        "integration_credentials",
        sa.Column(
            "budget_alert_triggered_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("integration_credentials", "budget_alert_triggered_at")
    op.drop_column("integration_credentials", "budget_alert_threshold_percent")
