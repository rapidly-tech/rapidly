"""add workflow_versions table and FK on workflows.current_version_id

Implements M4.1b of M4_EXECUTION.md. Creates the
``workflow_versions`` table (immutable append-only snapshots) and
adds the deferred FK constraint on ``workflows.current_version_id``
that M4.1a's migration intentionally left off.

Revision ID: 21aa9b69f43b
Revises: f24475bd0646
Create Date: 2026-05-25 23:29:11.992698
"""

import sqlalchemy as sa
from alembic import op

# Rapidly Custom Imports

# revision identifiers, used by Alembic.
revision = "21aa9b69f43b"
down_revision = "f24475bd0646"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("graph_json", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "workflow_id",
            "version_number",
            name="uq_workflow_versions_workflow_version",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_workflow_versions_workflow_id"),
        "workflow_versions",
        ["workflow_id"],
    )
    op.create_index(
        op.f("ix_workflow_versions_created_by_id"),
        "workflow_versions",
        ["created_by_id"],
    )

    # Deferred FK that M4.1a omitted on workflows.current_version_id
    # because the target table didn't exist yet.
    op.create_foreign_key(
        "fk_workflows_current_version_id",
        "workflows",
        "workflow_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_workflows_current_version_id",
        "workflows",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_workflow_versions_created_by_id"),
        table_name="workflow_versions",
    )
    op.drop_index(
        op.f("ix_workflow_versions_workflow_id"),
        table_name="workflow_versions",
    )
    op.drop_table("workflow_versions")
