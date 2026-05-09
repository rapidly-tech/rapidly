"""Apply pending Rapidly database schema migrations via Alembic."""

from shared import (
    Context,
    SERVER_DIR,
    console,
    run_command,
    step_status,
)

NAME = "Applying database migrations"


def run(ctx: Context) -> bool:
    """Execute any outstanding database migrations for the Rapidly schema."""
    with console.status("[bold][rapidly] Applying database migrations...[/bold]"):
        result = run_command(
            ["uv", "run", "task", "db_migrate"], cwd=SERVER_DIR, capture=True
        )
        if result and result.returncode == 0:
            step_status(True, "Database migrations", "applied successfully")
            return True
        else:
            step_status(False, "Database migrations", "failed")
            if result:
                console.print(f"[dim]{result.stderr}[/dim]")
            return False
