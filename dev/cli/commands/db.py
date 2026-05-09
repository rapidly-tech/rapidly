"""Rapidly database management commands for migrations and resets."""

import typer
from typing import Annotated

from shared import SERVER_DIR, console, run_command


def register(app: typer.Typer, prompt_setup: callable) -> None:
    db_app = typer.Typer(help="Rapidly database management commands")
    app.add_typer(db_app, name="db")

    @db_app.command("migrate")
    def db_migrate() -> None:
        """Apply pending database migrations."""
        console.print("\n[bold blue][rapidly] Applying database migrations[/bold blue]\n")

        result = run_command(["uv", "run", "task", "db_migrate"], cwd=SERVER_DIR, capture=False)
        if result and result.returncode == 0:
            console.print("\n[green]✓[/green] [rapidly] Migrations applied successfully")
        else:
            console.print("\n[red]✗[/red] [rapidly] Migration failed")
            raise typer.Exit(1)

    @db_app.command("reset")
    def db_reset(
        force: Annotated[
            bool, typer.Option("--force", "-f", help="Skip confirmation prompt")
        ] = False,
    ) -> None:
        """Drop and recreate the database to a clean state."""
        if not force:
            console.print("[yellow][rapidly] Warning: this will destroy all data in the database.[/yellow]")
            if not typer.confirm("Are you sure you want to continue?"):
                raise typer.Abort()

        console.print("\n[bold blue][rapidly] Resetting database to clean state[/bold blue]\n")

        result = run_command(["uv", "run", "task", "db_recreate"], cwd=SERVER_DIR, capture=False)
        if result and result.returncode == 0:
            console.print("\n[green]✓[/green] [rapidly] Database reset finished")
        else:
            console.print("\n[red]✗[/red] [rapidly] Database reset failed")
            raise typer.Exit(1)
