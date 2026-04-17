#!/usr/bin/env bash
# verify.sh — single-command local verification, runs every lint/type/test gate.
#
# Used by:
#   - developers, manually before `git push`
#   - .githooks/pre-push (if enabled via `git config core.hooksPath .githooks`)
#   - GitHub Actions CI as the push gate
#
# Exits non-zero on the first failure. Keep the order fast → slow so most
# problems surface in under a minute.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Colors — disabled when not a TTY (e.g. CI) to keep logs grep-friendly
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'; RESET=$'\033[0m'
else
  BOLD=''; DIM=''; RED=''; GREEN=''; RESET=''
fi

step() { echo; echo "${BOLD}→ $1${RESET}"; }
ok()   { echo "${GREEN}✓${RESET} $1"; }
fail() { echo "${RED}✗ $1${RESET}" >&2; exit 1; }

# ── Preflight ────────────────────────────────────────────────────────────
step "Preflight"

command -v uv       >/dev/null || fail "uv is not installed — see DEVELOPMENT.md"
command -v pnpm     >/dev/null || fail "pnpm is not installed — see DEVELOPMENT.md"
command -v docker   >/dev/null || fail "docker is not installed — see DEVELOPMENT.md"

# Infra must be up for backend tests that hit Postgres/Redis
running_services=$(docker compose -f server/docker-compose.yml ps --services --filter status=running 2>/dev/null || true)
for required in db redis; do
  if ! echo "$running_services" | grep -qx "$required"; then
    fail "Docker infra not running (missing '$required') — start with: cd server && docker compose up -d"
  fi
done
ok "toolchain + infra ready"

# ── Backend ──────────────────────────────────────────────────────────────
step "Backend lint"
( cd server && uv run task lint_check )
ok "backend lint"

step "Backend types (mypy)"
( cd server && uv run task lint_types )
ok "backend types"

step "Backend tests (fast mode, excluding integrations)"
# Excludes tests/integrations/* which depend on external services
# (Tinybird, Stripe, etc.). Those run in CI where creds are provisioned.
# To run them locally: cd server && uv run task test_fast
( cd server && RAPIDLY_ENV=testing uv run python -m pytest \
    --ignore=tests/integrations \
    -n auto -p no:sugar --no-cov )
ok "backend tests"

# ── Frontend ─────────────────────────────────────────────────────────────
step "Frontend typecheck"
( cd clients && pnpm typecheck )
ok "frontend typecheck"

step "Frontend lint"
( cd clients && pnpm lint )
ok "frontend lint"

step "Frontend tests"
( cd clients && pnpm test )
ok "frontend tests"

# ── E2E (placeholder until Playwright lands) ─────────────────────────────
# E2E multi-peer harness is added in the PR that ships the first new chamber
# (Screen / Messages / Call / etc.) — it only becomes meaningful then.
# Until then, skip with a clear marker so anyone grepping verify.sh can find it.
step "E2E (placeholder)"
echo "${DIM}  skipped — Playwright harness lands with the first chamber PR${RESET}"

# ── Done ────────────────────────────────────────────────────────────────
echo
echo "${BOLD}${GREEN}✓ All local checks passed.${RESET}"
echo "${DIM}  Append to your PR description: \"✓ local verify passed at $(git rev-parse --short HEAD)\"${RESET}"
