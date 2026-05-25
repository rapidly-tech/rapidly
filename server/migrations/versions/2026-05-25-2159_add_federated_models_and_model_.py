"""add federated_models and model_disciplines tables

Implements M3.1 of M3_EXECUTION.md (scaffold half). Creates the
two tables that back the Viewer chamber's domain. The IfcOpenShell
parser worker that flips ``status='uploaded'`` → ``'ready'`` ships
in M3.1b along with the system-deps it needs.

Revision ID: b548ffe17236
Revises: e5da4a23c32a
Create Date: 2026-05-25 21:59:18.259159
"""

import sqlalchemy as sa
from alembic import op

# Rapidly Custom Imports
from rapidly.core.extensions.sqlalchemy import StringEnum
from rapidly.models.federated_model import ModelStatus

# revision identifiers, used by Alembic.
revision = "b548ffe17236"
down_revision = "e5da4a23c32a"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.create_table(
        "federated_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), nullable=False),
        sa.Column("xkt_file_id", sa.Uuid(), nullable=True),
        sa.Column("status", StringEnum(ModelStatus, length=16), nullable=False),
        sa.Column("units", sa.String(length=8), nullable=True),
        sa.Column("element_count", sa.Integer(), nullable=True),
        sa.Column("bbox", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_file_id"], ["files.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["xkt_file_id"], ["files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_federated_models_project_id"),
        "federated_models",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_federated_models_source_file_id"),
        "federated_models",
        ["source_file_id"],
    )
    op.create_index(
        op.f("ix_federated_models_xkt_file_id"),
        "federated_models",
        ["xkt_file_id"],
    )

    op.create_table(
        "model_disciplines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("element_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["model_id"], ["federated_models.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_model_disciplines_model_id"),
        "model_disciplines",
        ["model_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_model_disciplines_model_id"), table_name="model_disciplines")
    op.drop_table("model_disciplines")
    op.drop_index(
        op.f("ix_federated_models_xkt_file_id"), table_name="federated_models"
    )
    op.drop_index(
        op.f("ix_federated_models_source_file_id"), table_name="federated_models"
    )
    op.drop_index(op.f("ix_federated_models_project_id"), table_name="federated_models")
    op.drop_table("federated_models")
