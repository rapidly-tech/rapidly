"""Stream or display logs from Rapidly infrastructure Docker containers."""

import os
from typing import Annotated, Optional

import typer

from shared import SERVER_DIR, console


def register(app: typer.Typer, prompt_setup: callable) -> None:
    @app.command()
    def logs(
        service: Annotated[
            Optional[str], typer.Argument(help="Service name (db, redis, minio, tinybird)")
        ] = None,
        follow: Annotated[
            bool, typer.Option("--follow", "-f", help="Continuously stream log output")
        ] = True,
        tail: Annotated[
            int, typer.Option("--tail", "-n", help="Number of recent lines to display")
        ] = 100,
    ) -> None:
        """Stream logs from Rapidly's Docker containers."""
        cmd = ["docker", "compose", "logs"]

        # Append follow flag if streaming is requested
        if follow:
            cmd.append("-f")

        cmd.extend(["--tail", str(tail)])

        if service:
            cmd.append(service)

        service_label = f" for {service}" if service else ""
        console.print(f"[dim][rapidly] Displaying logs{service_label}...[/dim]\n")

        os.chdir(SERVER_DIR)
        os.execvp(cmd[0], cmd)
