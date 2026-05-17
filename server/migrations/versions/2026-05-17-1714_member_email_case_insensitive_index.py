"""member_email_case_insensitive_index

Replace the case-sensitive UNIQUE ``(customer_id, email)`` constraint on
``members`` with a case-insensitive unique index on
``(customer_id, lower(email))``.  Without this, a customer could end up
with two members "Alice@Example.com" and "alice@example.com" — the
application layer treats them as one (see
``rapidly/identity/member/queries.py``), so the DB constraint must
agree.

Revision ID: 8a4f2c7e1b09
Revises: 27ed2e68876f
Create Date: 2026-05-17 17:14:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "8a4f2c7e1b09"
down_revision = "27ed2e68876f"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.drop_constraint("members_customer_id_email_key", "members", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX members_customer_id_email_key "
        "ON members (customer_id, lower(email))"
    )


def downgrade() -> None:
    op.drop_index("members_customer_id_email_key", table_name="members")
    op.create_unique_constraint(
        "members_customer_id_email_key",
        "members",
        ["customer_id", "email"],
        postgresql_nulls_not_distinct=True,
    )
