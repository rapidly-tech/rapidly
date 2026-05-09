"""Launch the Rapidly frontend web application in development mode."""

import os
from typing import Annotated, Optional

import typer

from shared import (
    CLIENTS_DIR,
    DEFAULT_WEB_PORT,
    console,
    find_available_port,
    is_port_in_use,
)


def register(app: typer.Typer, prompt_setup: callable) -> None:
    @app.command()
    def web(
        port: Annotated[
            Optional[int], typer.Option("--port", "-p", help="Port number for the dev server")
        ] = None,
    ) -> None:
        """Launch the Rapidly Next.js frontend dev server with Turbopack."""
        if not prompt_setup():
            raise typer.Exit(1)

        target_port = port or DEFAULT_WEB_PORT

        # Resolve port conflicts automatically when no explicit port was given
        if is_port_in_use(target_port):
            if port:
                console.print(f"[red][rapidly] Port {target_port} is already occupied[/red]")
                raise typer.Exit(1)
            else:
                new_port = find_available_port(target_port)
                console.print(f"[yellow][rapidly] Port {target_port} occupied, switching to {new_port}[/yellow]")
                target_port = new_port

        console.print(f"\n[bold blue][rapidly] Starting frontend dev server on port {target_port}[/bold blue]\n")

        web_app_dir = CLIENTS_DIR / "apps" / "web"
        os.chdir(web_app_dir)

        cmd = ["pnpm", "next", "dev", "--port", str(target_port), "--turbopack"]
        os.execvp(cmd[0], cmd)
