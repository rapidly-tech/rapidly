"""agents: integration_credentials table

Adds per-workspace credential storage for outbound LLM / embedding
provider API calls. Implements M4.7a — the credential model. The
consumer wiring (embedder + LLM handler reading from
``IntegrationCredential`` instead of ``os.environ``) lands in M4.7b.

The ``secret_encrypted`` column stores Fernet-encrypted plaintext;
the helper module (``rapidly.agents.integration_credential.queries``)
owns the encrypt / decrypt roundtrip so the model itself can't leak.

A partial unique index pins one default per (workspace, provider)
pair — workflows that don't name a specific credential get the
default by lookup. Operators rotating credentials should ``DELETE``
the old row first to free the slot or use ``UPDATE ... is_default``
on the new row (the partial index will deny a second default).

Revision ID: c8c2f17d3a91
Revises: 0ea0d9668ef2
Create Date: 2026-05-26 22:40:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c8c2f17d3a91"
down_revision = "0ea0d9668ef2"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_integration_credentials_workspace_id"),
        "integration_credentials",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_integration_credentials_provider"),
        "integration_credentials",
        ["provider"],
    )
    # Partial unique index: only one row may have
    # ``is_default=true`` per (workspace, provider). Excludes
    # soft-deleted rows so that a re-create can take the slot
    # back without operator hand-wiring.
    op.execute(
        "CREATE UNIQUE INDEX ix_integration_credentials_default_per_provider "
        "ON integration_credentials (workspace_id, provider) "
        "WHERE is_default = true AND deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_integration_credentials_default_per_provider")
    op.drop_index(
        op.f("ix_integration_credentials_provider"),
        table_name="integration_credentials",
    )
    op.drop_index(
        op.f("ix_integration_credentials_workspace_id"),
        table_name="integration_credentials",
    )
    op.drop_table("integration_credentials")
