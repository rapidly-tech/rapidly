"""Configure the correct Node.js version for Rapidly using nvm."""

import os
from pathlib import Path

from shared import (
    Context,
    ROOT_DIR,
    check_command_exists,
    console,
    get_command_version,
    run_command,
    step_status,
)

NAME = "Configuring Node.js version"

REQUIRED_NODE_MAJOR = 24


def is_nvm_installed() -> bool:
    """Verify that nvm is present on the system."""
    nvm_dir = Path.home() / ".nvm"
    return nvm_dir.exists() and (nvm_dir / "nvm.sh").exists()


def install_nvm() -> bool:
    """Download and run the official nvm installation script."""
    console.print("  [dim][rapidly] Setting up nvm...[/dim]")
    result = run_command(
        ["bash", "-c", "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"],
        capture=True,
    )
    return result is not None and result.returncode == 0


def run_nvm_install_node() -> bool:
    """Install the Node.js version specified in .nvmrc via nvm."""
    nvm_dir = Path.home() / ".nvm"
    nvm_script = nvm_dir / "nvm.sh"

    if not nvm_script.exists():
        return False

    cmd = f'source "{nvm_script}" && nvm install'
    result = run_command(["bash", "-c", cmd], cwd=ROOT_DIR, capture=True)
    return result is not None and result.returncode == 0


def activate_nvm_node() -> bool:
    """Make the nvm-managed Node binary available by prepending its directory to PATH."""
    nvm_dir = Path.home() / ".nvm"
    nvm_script = nvm_dir / "nvm.sh"

    if not nvm_script.exists():
        return False

    cmd = f'source "{nvm_script}" && nvm which current'
    result = run_command(["bash", "-c", cmd], cwd=ROOT_DIR, capture=True)

    if result and result.returncode == 0 and result.stdout.strip():
        node_path = Path(result.stdout.strip())
        if node_path.exists():
            bin_dir = str(node_path.parent)
            current_path = os.environ.get("PATH", "")
            if bin_dir not in current_path:
                os.environ["PATH"] = f"{bin_dir}:{current_path}"
            return True
    return False


def install_pnpm() -> bool:
    """Set up pnpm through corepack, falling back to npm global install."""
    result = run_command(["corepack", "enable"], capture=True)
    if result and result.returncode == 0:
        result = run_command(["corepack", "prepare", "pnpm@latest", "--activate"], capture=True)
        if result and result.returncode == 0:
            return True

    # Fallback to npm global install
    result = run_command(["npm", "install", "-g", "pnpm"], capture=True)
    return result is not None and result.returncode == 0


def run(ctx: Context) -> bool:
    """Ensure the required Node.js version is installed and active for Rapidly."""
    nvmrc_path = ROOT_DIR / ".nvmrc"

    # Generate .nvmrc when it does not already exist
    if not nvmrc_path.exists():
        nvmrc_path.write_text(f"{REQUIRED_NODE_MAJOR}\n")
        step_status(True, "Created .nvmrc", f"Node {REQUIRED_NODE_MAJOR}")
    else:
        step_status(True, ".nvmrc exists", nvmrc_path.read_text().strip())

    # Determine the currently active Node.js major version
    current_node_version = get_command_version("node")
    current_node_major = None
    if current_node_version:
        try:
            current_node_major = int(current_node_version.lstrip("v").split(".")[0])
        except ValueError:
            pass

    if current_node_major == REQUIRED_NODE_MAJOR:
        step_status(True, "Node version", f"v{current_node_major} (matches required)")
        return True

    # The active Node version does not match what Rapidly needs
    if current_node_major:
        console.print(f"  [yellow][rapidly] Node {current_node_major} detected, but {REQUIRED_NODE_MAJOR} is required[/yellow]")
    else:
        console.print(f"  [yellow][rapidly] Node not found, will install {REQUIRED_NODE_MAJOR}...[/yellow]")

    # Set up nvm if it is not yet installed
    if not is_nvm_installed():
        with console.status("[bold][rapidly] Installing nvm...[/bold]"):
            if install_nvm():
                step_status(True, "nvm", "installed")
            else:
                step_status(False, "nvm", "installation failed")
                console.print("  [dim][rapidly] Install manually: https://github.com/nvm-sh/nvm[/dim]")
                return False

    # Install the required Node.js version
    with console.status(f"[bold][rapidly] Installing Node {REQUIRED_NODE_MAJOR} via nvm...[/bold]"):
        if run_nvm_install_node():
            step_status(True, f"Node {REQUIRED_NODE_MAJOR}", "installed via nvm")
        else:
            step_status(False, f"Node {REQUIRED_NODE_MAJOR}", "installation failed")
            console.print(f"  [dim][rapidly] Try manually: nvm install {REQUIRED_NODE_MAJOR}[/dim]")
            return False

    # Activate the nvm-managed Node for this session
    if activate_nvm_node():
        step_status(True, "Node activated", "added to PATH for this session")
    else:
        console.print("[yellow][rapidly] Could not activate Node automatically.[/yellow]")
        console.print("Run: [bold]source ~/.nvm/nvm.sh && nvm use[/bold]")
        console.print("Then run [bold]dev up[/bold] again.")
        return False

    # Ensure pnpm is available now that Node is ready
    if not check_command_exists("pnpm"):
        console.print("  [yellow][rapidly] Setting up pnpm...[/yellow]")
        if install_pnpm():
            version = get_command_version("pnpm")
            step_status(True, "pnpm", f"installed ({version})" if version else "installed")
        else:
            step_status(False, "pnpm", "installation failed")
            return False

    return True
