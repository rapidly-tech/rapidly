"""Install Rapidly client-side JavaScript dependencies via pnpm."""

from shared import (
    Context,
    CLIENTS_DIR,
    check_node_modules_exists,
    console,
    run_command,
    step_status,
)

NAME = "Installing JS dependencies"


def run(ctx: Context) -> bool:
    """Install the Rapidly frontend dependencies using pnpm."""
    # Re-use existing node_modules unless a clean setup was requested
    if check_node_modules_exists() and not ctx.clean:
        step_status(True, "node_modules", "exists")
        return True

    with console.status("[bold][rapidly] Running pnpm install...[/bold]"):
        result = run_command(["pnpm", "install"], cwd=CLIENTS_DIR, capture=True)
        if result and result.returncode == 0:
            step_status(True, "pnpm install", "completed successfully")
            return True
        else:
            step_status(False, "pnpm install", "failed")
            if result:
                console.print(f"[dim]{result.stderr}[/dim]")
            return False
