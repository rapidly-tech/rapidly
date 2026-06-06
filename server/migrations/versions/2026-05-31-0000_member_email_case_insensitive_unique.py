"""replace case-sensitive members unique with case-insensitive partial

Revision ID: a3f6d9e21b48
Revises: e7d4ba29c8f1
Create Date: 2026-05-31 00:00:00.000000

Replaces the case-sensitive ``(customer_id, email)`` UNIQUE
constraint with a case-insensitive partial UNIQUE INDEX on
``(customer_id, lower(email)) WHERE deleted_at IS NULL``.

Two semantic improvements:

1. Case-insensitive: ``Alice@x.com`` and ``alice@x.com`` for the
   same customer are now treated as the same member. Matches
   the case-folded lookup pattern PR #854 added at the query
   layer (now finally enforced at the DB layer).

2. Partial on ``deleted_at IS NULL``: soft-deleted rows don't
   participate in the unique constraint, so an operator can
   soft-delete a member and re-create one with the same email
   (legitimate when somebody leaves + rejoins).

OPERATOR PREREQUISITE: this migration WILL FAIL if duplicate
active ``(customer_id, lower(email))`` rows exist. Run
``find_case_insensitive_email_duplicates`` (PR #866) +
``auto_dedupe_case_insensitive_email_duplicates`` (PR #867)
FIRST. The PR description has the operator workflow.

Drops the now-redundant non-unique index ``ix_members_customer
_id_email_lower`` (PR #859, revision e7d4ba29c8f1) — the new
unique index supersedes it (Postgres uses the unique for the
case-insensitive lookups too).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a3f6d9e21b48"
down_revision = "e7d4ba29c8f1"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    # 1. Drop the case-sensitive UNIQUE constraint. Operators
    #    must have run the dedupe script first (see module
    #    docstring) — otherwise step 3 would fail and roll
    #    back, but dropping this constraint first is harmless.
    op.drop_constraint("members_customer_id_email_key", "members", type_="unique")

    # 2. Drop the non-unique perf index added by PR #859 —
    #    the new unique partial index below supersedes it.
    op.drop_index("ix_members_customer_id_email_lower", table_name="members")

    # 3. Create the case-insensitive partial UNIQUE index.
    #    Postgres syntax: a functional UNIQUE INDEX with a
    #    WHERE clause. Alembic doesn't fully expose the WHERE
    #    via ``create_index`` for unique constraints + functional
    #    indexes together, so we drop to raw SQL for clarity.
    op.execute(
        """
        CREATE UNIQUE INDEX ix_members_customer_id_email_lower_active
        ON members (customer_id, lower(email))
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    # Reverse: drop the new partial unique, restore the perf
    # index from PR #859 + the original UNIQUE constraint.
    op.execute("DROP INDEX ix_members_customer_id_email_lower_active")
    op.execute(
        """
        CREATE INDEX ix_members_customer_id_email_lower
        ON members (customer_id, lower(email))
        """
    )
    op.create_unique_constraint(
        "members_customer_id_email_key",
        "members",
        ["customer_id", "email"],
        postgresql_nulls_not_distinct=True,
    )
