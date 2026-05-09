"""Bring up the Rapidly infrastructure stack (PostgreSQL, Redis, Minio) via Docker Compose."""

from shared import (
    Context,
    SERVER_DIR,
    console,
    run_command,
    step_status,
)

NAME = "Starting Rapidly infrastructure"


def get_docker_compose_status() -> dict[str, bool]:
    """Query Docker Compose for the current state of each service container."""
    result = run_command(
        ["docker", "compose", "ps", "--format", "{{.Name}} {{.State}}"],
        cwd=SERVER_DIR,
        capture=True,
    )
    status = {}
    if result and result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    state = parts[1].lower()
                    status[name] = state == "running"
    return status


def run(ctx: Context) -> bool:
    """Launch the Docker Compose services required by Rapidly."""
    docker_status = get_docker_compose_status()
    containers_running = any(docker_status.values()) if docker_status else False

    if containers_running and not ctx.clean:
        step_status(True, "Docker containers", "already running")
        return True

    with console.status("[bold][rapidly] Bringing up PostgreSQL, Redis, Minio...[/bold]"):
        result = run_command(
            ["docker", "compose", "up", "-d"],
            cwd=SERVER_DIR,
            capture=True,
        )

    if result and result.returncode == 0:
        # Report which services came up successfully
        new_status = get_docker_compose_status()
        services = [name.split("-")[-1] for name in new_status.keys() if new_status.get(name)]
        detail = f"started ({', '.join(services)})" if services else "started"
        step_status(True, "Docker containers", detail)
        return True
    else:
        step_status(False, "Docker containers", "failed to start")
        if result and result.stderr:
            console.print(f"[dim]{result.stderr}[/dim]")
        if result and result.stdout:
            console.print(f"[dim]{result.stdout}[/dim]")
        return False
