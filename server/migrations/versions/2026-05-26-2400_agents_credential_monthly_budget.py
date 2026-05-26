"""agents: monthly_budget_tokens on integration_credentials

Adds an optional per-credential monthly token cap. Nullable =
no budget. The usage rollup API in M4.7e/f gains a /budgets
endpoint that joins this column against month-to-date token
consumption per credential.

We store tokens, not dollars: provider price tables drift, and
operators may negotiate per-tenant rates. The dashboard converts
tokens to dollars at display time using whatever rate card is
configured.

Revision ID: f9d3e54b8e21
Revises: e1f7a23b4d50
Create Date: 2026-05-26 23:55:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f9d3e54b8e21"
down_revision = "e1f7a23b4d50"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integration_credentials",
        sa.Column("monthly_budget_tokens", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("integration_credentials", "monthly_budget_tokens")
