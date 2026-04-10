"""Generate Rapidly environment configuration files for server and web client."""

from shared import (
    Context,
    CLIENTS_DIR,
    ROOT_DIR,
    SERVER_DIR,
    check_env_file_exists,
    run_command,
    step_status,
)

NAME = "Generating environment files"


def run(ctx: Context) -> bool:
    """Create .env files for the Rapidly server and web client via setup-environment."""
    server_env_exists = check_env_file_exists(SERVER_DIR / ".env")
    web_env_exists = check_env_file_exists(CLIENTS_DIR / "apps" / "web" / ".env.local")

    # Skip generation when both env files are already present (unless --clean was passed)
    if server_env_exists and web_env_exists and not ctx.clean:
        step_status(True, "Environment files", "already present")
        return True

    setup_script = ROOT_DIR / "dev" / "setup-environment"
    result = run_command([str(setup_script)], capture=False)

    if result and result.returncode == 0:
        step_status(True, "Environment files", "generated successfully")
        return True
    else:
        step_status(False, "Environment files", "generation failed")
        return False
