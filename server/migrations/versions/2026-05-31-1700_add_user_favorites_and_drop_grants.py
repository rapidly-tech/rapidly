"""add user_favorites table + drop auto-grants for project_pages and user_favorites

The ``user_favorites`` model (PR #629 / commit ``39c1b27``) shipped to
``main`` without a corresponding Alembic migration. Tests pass because
the test database uses ``create_all`` on model metadata, but
``alembic upgrade head`` in production / CI would NOT have the table.

This migration:

  1. Drops the auto-applied ``rapidly_read.SELECT`` grant on
     ``project_pages`` (created in revision ``27ed2e68876f`` —
     missed in that migration's own ``drop_entity`` cleanup).
  2. Creates the ``user_favorites`` table to match the
     ``rapidly/models/user_favorite.py`` declaration.
  3. Drops the auto-applied ``rapidly_read.SELECT`` grant on the
     just-created ``user_favorites``. Deviates from the
     "drop grants one migration later" autogenerate pattern but
     leaves the schema in sync after this single revision.

Without this, ``alembic check`` flags drift on both tables and
the merge train is blocked.

Revision ID: a3f6d9e21b48
Revises: 27ed2e68876f
Create Date: 2026-05-31 17:00:00.000000

"""

from enum import StrEnum

import sqlalchemy as sa
from alembic import op
from alembic_utils.pg_grant_table import PGGrantTable

from rapidly.core.extensions.sqlalchemy.types import StringEnum


# ``UserFavoriteEntityType`` and its model were removed in M1.5 along
# with the user_favorites table. This migration still references the
# enum it originally created, so keep a local copy — migrations must
# stay loadable after the model code is deleted.
class UserFavoriteEntityType(StrEnum):
    project = "project"
    cycle = "cycle"
    module = "module"
    page = "page"


# revision identifiers, used by Alembic.
revision = "a3f6d9e21b48"
down_revision = "27ed2e68876f"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    # Drop the auto-grant on project_pages — the previous migration
    # (27ed2e68876f) created the table but did not drop the grant
    # auto-applied by ALTER DEFAULT PRIVILEGES from the initial
    # schema migration.
    public_project_pages_rapidly_read_select = PGGrantTable(
        schema="public",
        table="project_pages",
        columns=[
            "access",
            "archived_at",
            "created_at",
            "deleted_at",
            "description_binary",
            "description_html",
            "description_json",
            "id",
            "is_locked",
            "modified_at",
            "name",
            "owner_id",
            "parent_id",
            "project_id",
            "slug",
        ],
        role="rapidly_read",
        grant="SELECT",
        with_grant_option=False,
    )
    op.drop_entity(public_project_pages_rapidly_read_select)

    op.create_table(
        "user_favorites",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity_type",
            StringEnum(UserFavoriteEntityType, length=16),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("user_favorites_user_id_fkey"),
            ondelete="cascade",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("user_favorites_pkey")),
        sa.UniqueConstraint(
            "user_id",
            "entity_type",
            "entity_id",
            name="user_favorites_user_id_entity_type_entity_id_key",
        ),
    )
    op.create_index(
        op.f("ix_user_favorites_created_at"),
        "user_favorites",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_favorites_deleted_at"),
        "user_favorites",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_favorites_entity_id"),
        "user_favorites",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_favorites_entity_type"),
        "user_favorites",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_favorites_user_id"),
        "user_favorites",
        ["user_id"],
        unique=False,
    )

    # Drop the auto-grant on the just-created user_favorites — see
    # the module docstring for why we do this in the same migration
    # rather than deferring to the next one.
    public_user_favorites_rapidly_read_select = PGGrantTable(
        schema="public",
        table="user_favorites",
        columns=[
            "created_at",
            "deleted_at",
            "entity_id",
            "entity_type",
            "id",
            "modified_at",
            "user_id",
        ],
        role="rapidly_read",
        grant="SELECT",
        with_grant_option=False,
    )
    op.drop_entity(public_user_favorites_rapidly_read_select)


def downgrade() -> None:
    # Recreate the user_favorites grant first (DEFAULT PRIVILEGES
    # would have applied it on table creation, so downgrade
    # restores that state before dropping the table).
    public_user_favorites_rapidly_read_select = PGGrantTable(
        schema="public",
        table="user_favorites",
        columns=[
            "created_at",
            "deleted_at",
            "entity_id",
            "entity_type",
            "id",
            "modified_at",
            "user_id",
        ],
        role="rapidly_read",
        grant="SELECT",
        with_grant_option=False,
    )
    op.create_entity(public_user_favorites_rapidly_read_select)

    op.drop_index(op.f("ix_user_favorites_user_id"), table_name="user_favorites")
    op.drop_index(op.f("ix_user_favorites_entity_type"), table_name="user_favorites")
    op.drop_index(op.f("ix_user_favorites_entity_id"), table_name="user_favorites")
    op.drop_index(op.f("ix_user_favorites_deleted_at"), table_name="user_favorites")
    op.drop_index(op.f("ix_user_favorites_created_at"), table_name="user_favorites")
    op.drop_table("user_favorites")

    # Recreate the project_pages grant so downgrade lands at the
    # pre-revision state (where the grant was present).
    public_project_pages_rapidly_read_select = PGGrantTable(
        schema="public",
        table="project_pages",
        columns=[
            "access",
            "archived_at",
            "created_at",
            "deleted_at",
            "description_binary",
            "description_html",
            "description_json",
            "id",
            "is_locked",
            "modified_at",
            "name",
            "owner_id",
            "parent_id",
            "project_id",
            "slug",
        ],
        role="rapidly_read",
        grant="SELECT",
        with_grant_option=False,
    )
    op.create_entity(public_project_pages_rapidly_read_select)
