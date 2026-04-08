# ─────────────────────────────────────────────────────────────────────
# Rapidly — multi-stage production image
#
# Stages:
#   1. emails        – compile the React-based email renderer into a
#                      standalone Node binary (via tsup/pkg).
#   2. backoffice    – bundle the admin UI's static assets (Vite).
#   3. ipinfo        – fetch the IP geolocation database at build time
#                      with integrity verification.
#   4. runtime       – the final Python image that serves the FastAPI
#                      application, background workers, and CLI tools.
# ─────────────────────────────────────────────────────────────────────

# ── 1. Email renderer ────────────────────────────────────────────────
FROM node:22-slim AS emails

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /app

COPY ./emails/pnpm-lock.yaml ./emails/package.json ./
RUN pnpm install --frozen-lockfile

COPY ./emails/src src/
COPY ./emails/tsconfig.json ./emails/tsup.config.js ./
RUN pnpm run build

# ── 2. Backoffice static assets ─────────────────────────────────────
FROM node:22-slim AS backoffice

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /app

COPY ./rapidly/admin/pnpm-lock.yaml ./rapidly/admin/package.json ./
RUN pnpm install --no-frozen-lockfile

COPY ./rapidly/admin/ .
RUN pnpm run build

# ── 3. IP geolocation data (optional) ───────────────────────────────
FROM alpine:3.21 AS ipinfo

RUN mkdir /data && echo "IPInfo DB skipped (no token provided)" > /data/README

# ── 4. Runtime ───────────────────────────────────────────────────────
FROM --platform=$BUILDPLATFORM python:3.14-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/rapidly-tech/rapidly"
LABEL org.opencontainers.image.description="Rapidly file-sharing platform"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# uv — fast Python package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_NO_SYNC=1

WORKDIR /app/server

# Create a non-root user for runtime security
RUN groupadd --gid 1001 rapidly && \
    useradd --uid 1001 --gid rapidly --shell /bin/bash --create-home rapidly

# Install system packages and Python dependencies in a single layer.
# tzdata-legacy: required for legacy IANA timezone identifiers (e.g. Asia/Calcutta).
RUN --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    redis \
    libpq-dev \
    tzdata-legacy \
  && uv sync --no-group dev --frozen \
  && uv tool install tinybird --python 3.13 \
  && apt-get purge -y --auto-remove build-essential \
  && rm -rf /var/lib/apt/lists/*

ENV PATH="/home/rapidly/.local/bin:$PATH"

ADD . /app/server/

# Email renderer binary
COPY --from=emails /app/bin/react-email-pkg /app/server/
ENV RAPIDLY_EMAIL_RENDERER_BINARY_PATH=/app/server/react-email-pkg

# Backoffice assets
COPY --from=backoffice /app/static /app/server/rapidly/admin/static
RUN ls -la /app/server/rapidly/admin/static

# IP geolocation database
COPY --from=ipinfo /data /data
ENV RAPIDLY_IP_GEOLOCATION_DATABASE_DIRECTORY_PATH=/data \
    RAPIDLY_IP_GEOLOCATION_DATABASE_NAME=country_asn.mmdb

# Ensure the non-root user owns the application files
RUN chown -R rapidly:rapidly /app /data

ARG RELEASE_VERSION
ENV RELEASE_VERSION=${RELEASE_VERSION}

USER rapidly
EXPOSE 10000
CMD ["uv", "run", "uvicorn", "rapidly.app:app", "--host", "0.0.0.0", "--port", "10000"]
