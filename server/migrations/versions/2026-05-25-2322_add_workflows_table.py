"""add workflows table

Implements M4.1a of M4_EXECUTION.md. Creates the ``workflows``
table — the agent runtime's root authoring entity. WorkflowVersion,
Run, and NodeRun ship in follow-up migrations alongside their own
submodules.

``current_version_id`` is a UUID column without a FK constraint
yet — the workflow_versions table doesn't exist until the
follow-up migration. The follow-up will alter this column to add
the FK at that point, keeping migrations linearisable.

Revision ID: f24475bd0646
Revises: b548ffe17236
Create Date: 2026-05-25 23:22:42.624007
"""

import sqlalchemy as sa
from alembic import op

# Rapidly Custom Imports

# revision identifiers, used by Alembic.
revision = "f24475bd0646"
down_revision = "b548ffe17236"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_workflows_workspace_id"),
        "workflows",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_workflows_project_id"),
        "workflows",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_workflows_current_version_id"),
        "workflows",
        ["current_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_workflows_current_version_id"), table_name="workflows"
    )
    op.drop_index(op.f("ix_workflows_project_id"), table_name="workflows")
    op.drop_index(op.f("ix_workflows_workspace_id"), table_name="workflows")
    op.drop_table("workflows")
