"""initial_rapidly_schema

Revision ID: d889e389c54b
Revises:
Create Date: 2026-03-31 01:00:22.104415

"""

import sqlalchemy as sa
from alembic import op
from alembic_utils.pg_extension import PGExtension

# Rapidly Custom Imports
from rapidly.models import Model
from rapidly.models.customer import (
    customers_search_vector_trigger,
    customers_search_vector_update_function,
    generate_customer_short_id_function,
)
from rapidly.models.share import (
    shares_search_vector_trigger,
    shares_search_vector_update_function,
)

# revision identifiers, used by Alembic.
revision = "d889e389c54b"
down_revision = None
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    # 1. Extensions
    op.create_entity(PGExtension(schema="public", signature="uuid-ossp"))
    op.create_entity(PGExtension(schema="public", signature="citext"))

    # 2. Sequence for customer short IDs
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS customer_short_id_seq"))

    # 3. PG functions (needed before table creation for column defaults)
    op.create_entity(generate_customer_short_id_function)
    op.create_entity(customers_search_vector_update_function)
    op.create_entity(shares_search_vector_update_function)

    # 4. All tables from SQLAlchemy models
    bind = op.get_bind()
    Model.metadata.create_all(bind)

    # 5. Triggers (require tables to exist)
    op.create_entity(customers_search_vector_trigger)
    op.create_entity(shares_search_vector_trigger)

    # 6. Grant read-only access to the read replica user (if it exists)
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rapidly_read') THEN "
            "EXECUTE 'GRANT USAGE ON SCHEMA public TO rapidly_read'; "
            "EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA public TO rapidly_read'; "
            "EXECUTE 'GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO rapidly_read'; "
            "EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO rapidly_read'; "
            "EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO rapidly_read'; "
            "END IF; "
            "END $$"
        )
    )


def downgrade() -> None:
    # Revoke read-only access (if role exists)
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rapidly_read') THEN "
            "EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON SEQUENCES FROM rapidly_read'; "
            "EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM rapidly_read'; "
            "EXECUTE 'REVOKE SELECT ON ALL SEQUENCES IN SCHEMA public FROM rapidly_read'; "
            "EXECUTE 'REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM rapidly_read'; "
            "EXECUTE 'REVOKE USAGE ON SCHEMA public FROM rapidly_read'; "
            "END IF; "
            "END $$"
        )
    )

    # Drop triggers
    op.drop_entity(shares_search_vector_trigger)
    op.drop_entity(customers_search_vector_trigger)

    # Drop all tables
    bind = op.get_bind()
    Model.metadata.drop_all(bind)

    # Drop functions
    op.drop_entity(shares_search_vector_update_function)
    op.drop_entity(customers_search_vector_update_function)
    op.drop_entity(generate_customer_short_id_function)

    # Drop sequence
    op.execute(sa.text("DROP SEQUENCE IF EXISTS customer_short_id_seq"))

    # Drop extensions
    op.drop_entity(PGExtension(schema="public", signature="citext"))
    op.drop_entity(PGExtension(schema="public", signature="uuid-ossp"))
