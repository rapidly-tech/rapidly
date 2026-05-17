"""drift_cleanup_revoke_default_privileges_and_drop_grants

The initial migration set ``ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO rapidly_read``, so every table created
afterward silently received a SELECT grant.  Nothing in the model
layer registers those grants via ``alembic_utils.register_entities``,
so ``alembic check`` reports them as drift and tries to drop them.

Past feature migrations have papered over the issue by including
auto-generated ``op.drop_entity`` calls for the previous tables'
grants — so by now only the two most-recent tables (project_pages,
user_favorites) still hold grants.  This migration stops the
bleeding:

  1. Revoke the default-privileges grant so future tables don't
     auto-receive a SELECT for rapidly_read.
  2. Drop the two remaining drift grants so ``alembic check``
     reaches a clean state.

If a future table genuinely needs rapidly_read access, the migration
that creates it can call ``op.create_entity(PGGrantTable(...))``
explicitly and register the entity via ``register_entities`` on the
corresponding model.

Revision ID: 78892dd0b0ef
Revises: 27ed2e68876f
Create Date: 2026-05-17 18:05:14.878487

"""

from alembic import op
from alembic_utils.pg_grant_table import PGGrantTable
from sqlalchemy import text as sql_text

# revision identifiers, used by Alembic.
revision = "78892dd0b0ef"
down_revision = "27ed2e68876f"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.execute(
        sql_text(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rapidly_read') THEN "
            "EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "REVOKE SELECT ON TABLES FROM rapidly_read'; "
            "END IF; "
            "END $$"
        )
    )

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

    op.execute(
        sql_text(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rapidly_read') THEN "
            "EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT ON TABLES TO rapidly_read'; "
            "END IF; "
            "END $$"
        )
    )
