"""Verify and install prerequisite tools needed by the Rapidly dev environment."""

import platform
import time

from shared import (
    Context,
    check_command_exists,
    console,
    get_command_version,
    run_command,
    step_status,
)

NAME = "Checking prerequisites"


def is_docker_running() -> bool:
    """Determine whether the Docker daemon is currently responsive."""
    result = run_command(["docker", "info"], capture=True)
    return result is not None and result.returncode == 0


def install_docker() -> bool:
    """Attempt to install Docker via Homebrew (macOS only)."""
    if platform.system() != "Darwin":
        console.print("  [dim][rapidly] Auto-install of Docker is only available on macOS[/dim]")
        console.print("  [dim][rapidly] Please install Docker manually: https://docs.docker.com/get-docker/[/dim]")
        return False

    if not check_command_exists("brew"):
        console.print("  [dim][rapidly] Homebrew is required first: https://brew.sh[/dim]")
        return False

    console.print("  [dim][rapidly] Installing Docker via Homebrew...[/dim]")
    result = run_command(["brew", "install", "--cask", "docker"], capture=False)
    return result is not None and result.returncode == 0


def start_docker() -> bool:
    """Try to launch the Docker daemon on macOS or Linux."""
    if platform.system() == "Darwin":
        result = run_command(["open", "-a", "Docker"], capture=True)
        if result and result.returncode == 0:
            with console.status("[bold][rapidly] Waiting for Docker daemon...[/bold]"):
                for _ in range(60):
                    time.sleep(2)
                    if is_docker_running():
                        return True
            return False
    elif platform.system() == "Linux":
        result = run_command(["sudo", "systemctl", "start", "docker"], capture=True)
        if result and result.returncode == 0:
            time.sleep(2)
            return is_docker_running()
    return False


def install_homebrew() -> bool:
    """Install the Homebrew package manager on macOS."""
    if platform.system() != "Darwin":
        return False

    console.print("  [dim][rapidly] Setting up Homebrew...[/dim]")
    result = run_command(
        ["bash", "-c", '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'],
        capture=False,
    )
    return result is not None and result.returncode == 0


def install_pnpm() -> bool:
    """Install pnpm via corepack, npm, or Homebrew (in that order)."""
    # Prefer corepack as the primary installation method
    if check_command_exists("corepack"):
        result = run_command(["corepack", "enable"], capture=True)
        if result and result.returncode == 0:
            result = run_command(["corepack", "prepare", "pnpm@latest", "--activate"], capture=True)
            if result and result.returncode == 0:
                return True

    # Fall back to global npm install
    if check_command_exists("npm"):
        result = run_command(["npm", "install", "-g", "pnpm"], capture=True)
        if result and result.returncode == 0:
            return True

    # Last resort: Homebrew on macOS
    if platform.system() == "Darwin" and check_command_exists("brew"):
        result = run_command(["brew", "install", "pnpm"], capture=True)
        return result is not None and result.returncode == 0

    return False


def run(ctx: Context) -> bool:
    """Verify that Docker, uv, pnpm, and Node.js are available for Rapidly development."""
    prereqs_ok = True
    system = platform.system()

    # Homebrew (macOS) -- required for installing other dependencies
    if system == "Darwin":
        if check_command_exists("brew"):
            step_status(True, "Homebrew", "installed")
        else:
            console.print("  [yellow][rapidly] Homebrew not detected, installing...[/yellow]")
            if install_homebrew():
                step_status(True, "Homebrew", "installed")
            else:
                step_status(False, "Homebrew", "installation failed - visit https://brew.sh")
                prereqs_ok = False

    # Docker -- needed for PostgreSQL, Redis, Minio
    if check_command_exists("docker"):
        if is_docker_running():
            step_status(True, "Docker", "running")
        else:
            console.print("  [yellow][rapidly] Docker is installed but not running, attempting to start...[/yellow]")
            if start_docker():
                step_status(True, "Docker", "started")
            else:
                step_status(False, "Docker", "failed to start - please launch Docker manually")
                prereqs_ok = False
    else:
        console.print("  [yellow][rapidly] Docker not detected, installing...[/yellow]")
        if install_docker():
            step_status(True, "Docker", "installed")
            console.print("  [yellow][rapidly] Launching Docker...[/yellow]")
            if start_docker():
                step_status(True, "Docker", "started")
            else:
                step_status(False, "Docker", "installed but could not start - please launch Docker manually")
                prereqs_ok = False
        else:
            step_status(False, "Docker", "installation failed")
            prereqs_ok = False

    # uv -- should already be present from the bootstrap wrapper
    version = get_command_version("uv")
    step_status(True, "uv", version or "")

    # pnpm -- JavaScript package manager
    if check_command_exists("pnpm"):
        version = get_command_version("pnpm")
        step_status(True, "pnpm", version or "")
    else:
        console.print("  [yellow][rapidly] pnpm not detected, installing...[/yellow]")
        if install_pnpm():
            version = get_command_version("pnpm")
            step_status(True, "pnpm", f"installed ({version})" if version else "installed")
        else:
            step_status(False, "pnpm", "installation failed - install manually: npm install -g pnpm")
            prereqs_ok = False

    # Node.js -- report current status; step 02 handles nvm-based installation
    if check_command_exists("node"):
        version = get_command_version("node")
        step_status(True, "Node.js", version or "")
    else:
        step_status(True, "Node.js", "not found (will be installed via nvm)")

    return prereqs_ok
