"""fix customer email index shape mismatch

Revision ID: b4e7c1d92a85
Revises: 27ed2e68876f
Create Date: 2026-05-31 01:00:00.000000

The model declared ``ix_customers_workspace_id_email_case_
insensitive`` as ``unique=True`` on columns ``(lower(email),
deleted_at)`` — but the NAME promised ``workspace_id`` was in
the column list. This is a real shape-mismatch bug:

- Multi-tenant intent: two workspaces should be able to
  have customers with the same email (different operators'
  customer bases). The constraint AS-DECLARED would
  prevent that — cross-workspace email reuse blocked.
- Workspace-scoped intent (what the name promised): each
  workspace can have AT MOST ONE active customer per
  email. That's the correct multi-tenant semantic.

This migration recreates the index with the correct columns
+ a partial ``WHERE deleted_at IS NULL`` clause (so soft-
deleted customers don't block re-creation, mirroring the
Member PR #868 pattern):

  CREATE UNIQUE INDEX ix_customers_workspace_id_email_case_insensitive
  ON customers (workspace_id, lower(email))
  WHERE deleted_at IS NULL;

Uses ``DROP INDEX IF EXISTS`` because the original index may
or may not be present in production (the model declaration
pre-dates the alembic baseline and no migration created it
explicitly). Either state is handled cleanly.

OPERATOR PREREQUISITE: if production HAS the old broken
index AND there were any cross-workspace email duplicates
that were prevented by it, those would now be allowed —
but the new constraint would also reject any in-workspace
duplicates, so review with a dedupe-finder query first:

  SELECT workspace_id, lower(email), COUNT(*)
  FROM customers
  WHERE deleted_at IS NULL
  GROUP BY workspace_id, lower(email)
  HAVING COUNT(*) > 1;

If this returns rows, the new unique index would fail at
creation time and roll back.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b4e7c1d92a85"
down_revision = "a3f6d9e21b48"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    # 1. Drop the old (possibly-present) index. IF EXISTS
    #    handles the "model declared it but no migration
    #    created it" case where production might not have it.
    op.execute("DROP INDEX IF EXISTS ix_customers_workspace_id_email_case_insensitive")

    # 2. Create the corrected index. Functional + partial
    #    + unique: alembic's create_index doesn't expose the
    #    WHERE clause for partial indexes alongside functional
    #    columns cleanly, so use raw SQL.
    op.execute(
        """
        CREATE UNIQUE INDEX ix_customers_workspace_id_email_case_insensitive
        ON customers (workspace_id, lower(email))
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    # Reverse: drop the corrected index, recreate the
    # original (broken-shape) declaration so a rollback
    # returns to the pre-migration state byte-for-byte.
    op.execute("DROP INDEX ix_customers_workspace_id_email_case_insensitive")
    op.execute(
        """
        CREATE UNIQUE INDEX ix_customers_workspace_id_email_case_insensitive
        ON customers (lower(email), deleted_at)
        """
    )
