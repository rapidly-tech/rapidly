"""Compile Rapidly shared packages (ui, client, checkout, customer-portal) via Turbo."""

from shared import (
    Context,
    CLIENTS_DIR,
    console,
    run_command,
    step_status,
)

NAME = "Building shared packages"

# The set of workspace packages that the Rapidly web app depends on
_PACKAGE_LIST = "ui, client, checkout, customer-portal"


def run(ctx: Context) -> bool:
    """Build the shared packages that the Rapidly web application relies on."""
    with console.status(f"[bold][rapidly] Building packages ({_PACKAGE_LIST})...[/bold]"):
        result = run_command(
            ["pnpm", "turbo", "run", "build", "--filter=./packages/*"],
            cwd=CLIENTS_DIR,
            capture=True,
        )
        if result and result.returncode == 0:
            step_status(True, "Packages built", _PACKAGE_LIST)
            return True
        else:
            step_status(False, "Package build", "failed")
            if result and result.stderr:
                # Show only the first 500 chars to avoid flooding the terminal
                console.print(f"[dim]{result.stderr[:500]}[/dim]")
            return False
