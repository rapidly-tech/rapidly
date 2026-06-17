"""add case-insensitive index on members.email

Revision ID: e7d4ba29c8f1
Revises: 27ed2e68876f
Create Date: 2026-05-30 09:30:00.000000

PR #854 made ``MemberRepository.get_by_customer_and_email`` +
``get_by_customer_id_and_email`` case-insensitive via
``func.lower(Member.email) == email.lower()``. The existing
``(customer_id, email)`` unique constraint is case-sensitive
so it can't serve the new lookup — Postgres would do a
sequential scan filtered by ``customer_id == X`` to find
the row.

This adds a non-unique B-tree index on ``(customer_id,
lower(email))`` so the case-insensitive lookup uses an
index. Stops short of REPLACING the case-sensitive unique
constraint (that would require a row-dedupe migration for
any legacy mixed-case duplicates and a separate product
decision — see PR #854's discussion).

Symmetric to the ``ix_users_email_case_insensitive`` index
declared on User in ``models/user.py:138``.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e7d4ba29c8f1"
down_revision = "27ed2e68876f"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    # CONCURRENTLY is preferred for production to avoid locking
    # the table during the build, but alembic-style ops run
    # inside a transaction by default which CONCURRENTLY
    # forbids. The members table is small (< 1M rows in any
    # realistic workspace) so a brief AccessShareLock on the
    # index build is acceptable.
    op.create_index(
        "ix_members_customer_id_email_lower",
        "members",
        ["customer_id", sa.text("lower(email)")],
        unique=False,
    )
    # Second index serves ``MemberRepository.list_by_email_and_
    # workspace`` (used by the customer-portal email-
    # disambiguation path). Without it, that query would scan
    # the workspace_id index then filter on lower(email) — for
    # workspaces with many members this is wasteful.
    op.create_index(
        "ix_members_workspace_id_email_lower",
        "members",
        ["workspace_id", sa.text("lower(email)")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_members_workspace_id_email_lower", table_name="members")
    op.drop_index("ix_members_customer_id_email_lower", table_name="members")
