"""Alembic migration environment for the Rapidly database.

Configures async PostgreSQL connectivity and autogenerate filtering
so that tables flagged with ``skip_autogenerate`` are left untouched.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from rapidly.config import settings
from rapidly.models import Model

# ── Alembic setup ──────────────────────────────────────────────────────

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Model.metadata

config.set_main_option(
    "sqlalchemy.url",
    # Escape %-signs so Alembic doesn't treat them as interpolation markers.
    settings.get_postgres_dsn("asyncpg").replace("%", "%%"),
)


# ── Autogenerate filter ───────────────────────────────────────────────


def include_object(object, name, type_, reflected, compare_to):
    """Skip tables and indexes marked with ``info={'skip_autogenerate': True}``."""
    if type_ in ("table", "index") and hasattr(object, "info"):
        if object.info.get("skip_autogenerate"):
            return False
    return True


# ── Offline / online runners ──────────────────────────────────────────


def run_migrations_offline() -> None:
    """Generate SQL script without connecting to the database."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Connect to the database and run migrations within a transaction."""
    configuration = config.get_section(config.config_ini_section)
    if not configuration:
        raise ValueError("No Alembic config found")

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
