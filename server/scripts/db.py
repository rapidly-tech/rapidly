"""Database management CLI for Rapidly.

Provides upgrade, recreate, reparent and wipe_data commands used by the
``uv run task db_*`` shortcuts defined in pyproject.toml and by the
clean-state-hetzner GitHub Actions workflow.
"""

import os
import re
import subprocess

import redis
import typer
from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy_utils import create_database, database_exists, drop_database

from rapidly.config import settings

cli = typer.Typer()


def get_sync_postgres_dsn() -> str:
    """Return a psycopg2 DSN with escaped ``%`` characters for Alembic."""
    return settings.get_postgres_dsn("psycopg2").replace("%", "%%")


def get_config() -> Config:
    """Build an Alembic ``Config`` pointing at the project's ``alembic.ini``."""
    config_file = os.path.join(os.path.dirname(__file__), "../alembic.ini")
    config = Config(config_file)
    config.set_main_option("sqlalchemy.url", get_sync_postgres_dsn())
    return config


def _reparent(force: bool = False) -> None:
    """Rebase a branch migration on top of the latest ``main`` head.

    When two developers create migrations concurrently, Alembic ends up
    with two heads.  This function detects which head belongs to ``main``
    and rewrites the local branch migration's ``down_revision`` to point
    at that head, collapsing the graph back into a single chain.
    """
    # Discover current Alembic heads
    p_out = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        capture_output=True,
        text=True,
    )
    p_out.check_returncode()
    heads = set(
        [line.removesuffix(" (head)") for line in p_out.stdout.strip().split("\n")]
    )

    if force:
        pass
    elif len(heads) == 1:
        print("[rapidly] Single head found — nothing to reparent.")
        return
    elif len(heads) > 2:
        print("[rapidly] More than 2 heads detected — manual resolution required.")
        return

    main_head = None
    branch_head = None
    main_migration_file = None
    branch_migration_file = None
    for head in heads:
        # `git grep {head} main -- "server/migrations/versions/*"`
        p_out = subprocess.run(
            ["git", "grep", "-l", head, "main", "--", "migrations/versions/*"],
            capture_output=True,
            text=True,
        )
        if p_out.returncode == 0:
            main_head = head
            main_migration_file = p_out.stdout.strip().removeprefix("main:")

    if main_head:
        heads.remove(main_head)

    for head in heads:
        # `git grep {head} HEAD -- "server/migrations/versions/*"`
        p_out = subprocess.run(
            ["git", "grep", "-l", head, "HEAD", "--", "migrations/versions/*"],
            capture_output=True,
            text=True,
        )
        if p_out.returncode == 0:
            branch_head = head
            branch_migration_file = p_out.stdout.strip().removeprefix("HEAD:")

    if (
        not main_head
        or not branch_head
        or not main_migration_file
        or not branch_migration_file
    ):
        return

    print(f"""
`main` head: {main_head} ({main_migration_file})
branch head: {branch_head} ({branch_migration_file})
""")

    re_down_revision = re.compile(r'down_revision = "([^"]+)"')

    # Rewrite the branch migration's down_revision to chain off main
    with open(branch_migration_file, "r+") as f:
        f_contents = f.read()

        previous_parent = list(re_down_revision.finditer(f_contents))[0].group(1)
        f_new_contents = re_down_revision.sub(
            f'down_revision = "{main_head}"', f_contents
        )
        f_new_contents = re.sub(
            "Revises: [a-f0-9]+", f"Revises: {main_head}", f_new_contents
        )

        print(f"Updating {branch_migration_file}")
        print(f'`down_revision` was "{previous_parent}"')
        print(f'`down_revision` updated to "{main_head}"')
        f.seek(0)
        f.write(f_new_contents)


def _upgrade(revision: str = "head") -> None:
    config = get_config()
    alembic_upgrade(config, revision)


def _recreate() -> None:
    assert_dev_or_testing()

    if database_exists(get_sync_postgres_dsn()):
        drop_database(get_sync_postgres_dsn())

    create_database(get_sync_postgres_dsn())
    _upgrade("head")


def _wipe_data() -> None:
    """TRUNCATE every public-schema table except alembic_version, then FLUSHDB.

    Used by the ``clean-state-hetzner`` GitHub Actions workflow as the
    implementation of a "factory reset" on the running production cluster.
    The Postgres schema and Alembic migration history are preserved so the
    install stays valid; running ``db_migrate`` afterwards is a no-op.

    Unlike :func:`_recreate`, this function intentionally does NOT call
    :func:`assert_dev_or_testing` — its caller, :func:`wipe_data`, gates on
    an explicit ``--confirm`` flag instead, so the same code path can be
    invoked from production.
    """
    # ── Postgres: TRUNCATE all public tables except alembic_version ──
    engine = create_engine(get_sync_postgres_dsn())
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename != 'alembic_version' "
                    "ORDER BY tablename"
                )
            )
            tables = [row[0] for row in result]
            print(f"[rapidly] Postgres: truncating {len(tables)} tables")
            for t in tables:
                print(f"  - {t}")

            conn.execute(
                text(
                    """
                    DO $$
                    DECLARE r RECORD;
                    BEGIN
                        FOR r IN
                            SELECT tablename FROM pg_tables
                            WHERE schemaname = 'public' AND tablename != 'alembic_version'
                        LOOP
                            EXECUTE 'TRUNCATE TABLE public.' || quote_ident(r.tablename) || ' RESTART IDENTITY CASCADE';
                        END LOOP;
                    END $$;
                    """
                )
            )
            print("[rapidly] Postgres: TRUNCATE complete (alembic_version preserved)")
    finally:
        engine.dispose()

    # ── Redis: full FLUSHDB ──
    r = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
    )
    try:
        before = r.dbsize()
        r.flushdb()
        after = r.dbsize()
        print(f"[rapidly] Redis: flushed {before} keys, dbsize now {after}")
    finally:
        r.close()


@cli.command()
def upgrade(
    revision: str = typer.Option("head", help="Which revision to upgrade to"),
) -> None:
    _upgrade(revision)


@cli.command()
def recreate() -> None:
    assert_dev_or_testing()
    _recreate()


@cli.command(
    help=(
        "Wipe all user data from the database (TRUNCATE every public-schema "
        "table except alembic_version) and FLUSHDB on Redis. Preserves the "
        "schema and migration history. Requires --confirm because this is "
        "irreversible and runs in any environment, including production."
    )
)
def wipe_data(
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="Required acknowledgement that this is an irreversible data wipe.",
    ),
) -> None:
    if not confirm:
        raise typer.BadParameter(
            "wipe_data requires --confirm. Every user, workspace, customer, "
            "file share, secret, Stripe Connect account link, event, webhook "
            "delivery and audit log row in the target database will be deleted."
        )
    print(f"[rapidly] Environment: {settings.ENV}")
    _wipe_data()


@cli.command(
    help="Try to move a conflicting head migration on the current branch on top o fthe latest migration on `main`"
)
def reparent(
    force: bool = typer.Option(
        False,
        "-f",
        "--force",
        help="Update latest migration even if there aren't multiple heads",
    ),
) -> None:
    _reparent(force=force)


def assert_dev_or_testing() -> None:
    if not (settings.is_development() or settings.is_testing()):
        raise RuntimeError(f"DANGER! You cannot run this script in {settings.ENV}!")


if __name__ == "__main__":
    cli()
