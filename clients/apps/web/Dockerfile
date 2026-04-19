# ─────────────────────────────────────────────────────────────────────
# Rapidly — Next.js frontend production image (standalone output)
#
# Build from the clients/ directory:
#   docker build -f apps/web/Dockerfile -t rapidly-web .
# ─────────────────────────────────────────────────────────────────────

# ── 1. Dependencies ──────────────────────────────────────────────────
FROM node:24-slim AS deps

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app

# Copy workspace root files
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json turbo.json ./

# Copy patches required by pnpm
COPY patches/ patches/

# Copy all package manifests so pnpm can resolve the workspace
COPY packages/client/package.json packages/client/
COPY packages/currency/package.json packages/currency/
COPY packages/customer-portal/package.json packages/customer-portal/
COPY packages/eslint-config/package.json packages/eslint-config/
COPY packages/mdx/package.json packages/mdx/
COPY packages/typescript-config/package.json packages/typescript-config/
COPY packages/ui/package.json packages/ui/
COPY apps/web/package.json apps/web/

RUN pnpm install --frozen-lockfile --ignore-scripts

# ── 2. Build ─────────────────────────────────────────────────────────
FROM node:24-slim AS builder

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app

# Copy dependencies from previous stage
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/packages/client/node_modules ./packages/client/node_modules
COPY --from=deps /app/packages/currency/node_modules ./packages/currency/node_modules
COPY --from=deps /app/packages/customer-portal/node_modules ./packages/customer-portal/node_modules
COPY --from=deps /app/packages/ui/node_modules ./packages/ui/node_modules
COPY --from=deps /app/packages/mdx/node_modules ./packages/mdx/node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules

# Copy all source code
COPY . .

# Create .env.production with correct URLs for the Next.js build.
# Next.js reads NEXT_PUBLIC_* from .env files, not Docker ENV vars.
ARG NEXT_PUBLIC_API_URL=https://api.rapidly.tech
ARG NEXT_PUBLIC_FRONTEND_BASE_URL=https://rapidly.tech
ARG NEXT_PUBLIC_POSTHOG_TOKEN=
ARG NEXT_PUBLIC_SENTRY_DSN=
# Gates the 6-chamber revolver landing at /. Baked in at build time
# (Next.js can't read env at request time for static pages). Default
# false so a local/dev build without the arg matches the historical
# file-sharing landing.
ARG NEXT_PUBLIC_REVOLVER_LANDING=false
# Gates the Collab E2EE UI (default-on behaviour lives in
# components/Collab/CollabHostClient + CollabGuestClient). Default
# true so production-style builds get E2EE without requiring an
# explicit build-arg; set to false only for a deliberate opt-out.
ARG NEXT_PUBLIC_COLLAB_E2EE=true
RUN printf 'NEXT_PUBLIC_API_URL=%s\nNEXT_PUBLIC_FRONTEND_BASE_URL=%s\nNEXT_PUBLIC_POSTHOG_TOKEN=%s\nNEXT_PUBLIC_SENTRY_DSN=%s\nNEXT_PUBLIC_REVOLVER_LANDING=%s\nNEXT_PUBLIC_COLLAB_E2EE=%s\n' \
  "${NEXT_PUBLIC_API_URL}" "${NEXT_PUBLIC_FRONTEND_BASE_URL}" "${NEXT_PUBLIC_POSTHOG_TOKEN}" "${NEXT_PUBLIC_SENTRY_DSN}" "${NEXT_PUBLIC_REVOLVER_LANDING}" "${NEXT_PUBLIC_COLLAB_E2EE}" \
  > apps/web/.env.production
ENV NEXT_TELEMETRY_DISABLED=1

# Build workspace packages first (client, currency, customer-portal, ui, etc.)
RUN pnpm --filter @rapidly-tech/client build
RUN pnpm --filter @rapidly-tech/currency build
RUN pnpm --filter @rapidly-tech/customer-portal build
RUN pnpm --filter @rapidly-tech/ui build

RUN pnpm --filter web build

# ── 3. Runtime ───────────────────────────────────────────────────────
FROM node:24-slim AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN groupadd --gid 1001 rapidly && \
    useradd --uid 1001 --gid rapidly --shell /bin/bash --create-home rapidly

# Copy the standalone output
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public

RUN chown -R rapidly:rapidly /app

USER rapidly
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "apps/web/server.js"]
