#! /bin/bash
# Rapidly devcontainer post-create hook.
# Installs Python tooling (uv), creates the test database, syncs server
# dependencies, generates dev JWKs, and installs frontend packages so the
# Rapidly workspace is ready to use immediately after container creation.

set -euo pipefail
set -x

# Setup uv
pip install -U pip uv

# Create test database
./dev/create-test-db

# Server setup
cd /workspace/server
uv sync
uv run task generate_dev_jwks
echo "🐻‍❄️✅ Server ready"

# Clients setup
cd /workspace/clients
pnpm install
echo "🐻‍❄️✅ Clients ready"

# Install uv
pip install -U uv

echo "🐻‍❄️✅ Setup complete"
