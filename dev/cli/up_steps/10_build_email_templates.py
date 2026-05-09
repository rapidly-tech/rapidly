"""Compile Rapidly transactional email templates from source."""

from shared import (
    Context,
    SERVER_DIR,
    check_email_binary_exists,
    console,
    run_command,
    step_status,
)

NAME = "Compiling email templates"


def run(ctx: Context) -> bool:
    """Build the Rapidly email templates used for transactional notifications."""
    # Skip rebuild if compiled templates are already present
    if check_email_binary_exists() and not ctx.clean:
        step_status(True, "Email templates", "already compiled")
        return True

    with console.status("[bold][rapidly] Compiling email templates...[/bold]"):
        result = run_command(
            ["uv", "run", "task", "emails"], cwd=SERVER_DIR, capture=True
        )
        if result and result.returncode == 0:
            step_status(True, "Email templates", "compiled")
            return True
        else:
            step_status(False, "Email templates", "compilation failed (non-critical)")
            if result:
                console.print(f"[dim]{result.stderr}[/dim]")
            # Email templates are not essential for basic development
            return True
