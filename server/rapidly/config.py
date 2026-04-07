"""Rapidly platform configuration.

Hydrates typed settings from environment variables via *pydantic-settings*.
The ``RAPIDLY_`` prefix is stripped automatically, so ``RAPIDLY_POSTGRES_HOST``
maps to ``Settings.POSTGRES_HOST``.

Settings are decomposed into descriptor dataclasses (``_DatabaseCfg``,
``_CacheCfg``, etc.) that are *inlined* into the main ``Settings`` class via
``model_validator``.  This keeps the flat env-var interface that
pydantic-settings requires while giving internal code typed sub-groups
through properties like ``settings.db`` and ``settings.cache``.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from annotated_types import Ge
from pydantic import (
    AfterValidator,
    Field,
    PostgresDsn,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from rapidly.core.jwk import JWKSFile

# ---------------------------------------------------------------------------
# Public enums
# ---------------------------------------------------------------------------


class Environment(StrEnum):
    """Deployment stage identifiers.

    ``testing`` is the local pytest runner; ``test`` is the hosted staging
    environment on Render.
    """

    development = "development"
    testing = "testing"
    sandbox = "sandbox"
    production = "production"
    test = "test"


class EmailSender(StrEnum):
    """Selects the outbound email transport."""

    logger = "logger"
    gmail = "gmail"


# ---------------------------------------------------------------------------
# Inline sub-group descriptors
# ---------------------------------------------------------------------------
# These frozen dataclasses give internal code a structured way to access
# groups of settings without changing the flat env-var surface.


@dataclass(frozen=True, slots=True)
class _DatabaseCfg:
    user: str
    pwd: str
    host: str
    port: int
    database: str
    pool_size: int
    sync_pool_size: int
    pool_recycle_seconds: int
    command_timeout_seconds: float
    stream_yield_per: int
    # Read replica (all-or-nothing)
    read_user: str | None
    read_pwd: str | None
    read_host: str | None
    read_port: int | None
    read_database: str | None

    def dsn(self, driver: Literal["asyncpg", "psycopg2"]) -> str:
        return str(
            PostgresDsn.build(
                scheme=f"postgresql+{driver}",
                username=self.user,
                password=self.pwd,
                host=self.host,
                port=self.port,
                path=self.database,
            )
        )

    @property
    def has_read_replica(self) -> bool:
        return all(
            (
                self.read_user,
                self.read_pwd,
                self.read_host,
                self.read_port,
                self.read_database,
            )
        )

    def read_dsn(self, driver: Literal["asyncpg", "psycopg2"]) -> str | None:
        if not self.has_read_replica:
            return None
        return str(
            PostgresDsn.build(
                scheme=f"postgresql+{driver}",
                username=self.read_user,
                password=self.read_pwd,
                host=self.read_host,
                port=self.read_port,
                path=self.read_database,
            )
        )


@dataclass(frozen=True, slots=True)
class _CacheCfg:
    host: str
    port: int
    db: int
    password: str | None

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass(frozen=True, slots=True)
class _FileSharingCfg:
    channel_ttl: int
    stun_server: str
    coturn_enabled: bool
    turn_host: str
    turn_port: int
    turn_tls_port: int
    turn_tls_enabled: bool
    turn_secret: str
    turn_credential_ttl: int
    platform_fee_percent: int
    min_price_cents: int
    max_price_cents: int
    paid_channel_ttl: int


@dataclass(frozen=True, slots=True)
class _ClamAVCfg:
    enabled: bool
    socket_path: str | None
    host: str
    port: int
    quarantine_bucket: str


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _validate_email_renderer_binary_path(value: Path) -> Path:
    """Verify that the compiled React-Email renderer is present at the given path."""
    if not value.exists() or not value.is_file():
        raise ValueError(
            f"""
        The provided email renderer binary path {value} is not a valid file path
        or does not exist.\n
        If you're in local development, you should build the email renderer binary
        by running the following command:\n
        uv run task emails\n
        """
        )
    return value


# ---------------------------------------------------------------------------
# Env-file resolution
# ---------------------------------------------------------------------------

_active_env: Environment = Environment(
    os.getenv("RAPIDLY_ENV", Environment.development)
)

_ENV_FILE_MAP: dict[Environment, str] = {
    Environment.testing: ".env.testing",
    Environment.test: ".env.test",
}
_env_file: str = _ENV_FILE_MAP.get(_active_env, ".env")

_binary_ext: str = ".exe" if os.name == "nt" else ""


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Central configuration container, hydrated from env vars.

    All fields are flat (as required by pydantic-settings), but sub-group
    descriptors are materialized lazily via properties so that internal code
    can access ``settings.db``, ``settings.cache``, etc.
    """

    model_config = SettingsConfigDict(
        env_prefix="rapidly_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_file=_env_file,
        extra="allow",
    )

    # -- Database (primary) ------------------------------------------------
    POSTGRES_USER: str = "rapidly"
    POSTGRES_PWD: str = "rapidly"
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_DATABASE: str = "rapidly"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_SYNC_POOL_SIZE: int = 1
    DATABASE_POOL_RECYCLE_SECONDS: int = 600
    DATABASE_COMMAND_TIMEOUT_SECONDS: float = 30.0
    DATABASE_STREAM_YIELD_PER: int = 100

    # -- Database (read replica) -------------------------------------------
    POSTGRES_READ_USER: str | None = None
    POSTGRES_READ_PWD: str | None = None
    POSTGRES_READ_HOST: str | None = None
    POSTGRES_READ_PORT: int | None = None
    POSTGRES_READ_DATABASE: str | None = None

    # -- Cache (Redis) -----------------------------------------------------
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # -- Object storage (S3 / Minio) --------------------------------------
    AWS_ACCESS_KEY_ID: str = "rapidly-development"
    AWS_SECRET_ACCESS_KEY: str = "rapidly123456789"
    AWS_REGION: str = "us-east-2"
    AWS_SIGNATURE_VERSION: str = "v4"
    S3_FILES_BUCKET_NAME: str = "rapidly-s3"
    S3_FILES_PUBLIC_BUCKET_NAME: str = "rapidly-s3-public"
    S3_FILES_PRESIGN_TTL: int = 3600
    S3_ENDPOINT_URL: str | None = None
    MINIO_USER: str = "rapidly"
    MINIO_PWD: str = "rapidlyrapidly"

    # -- Auth & secrets ----------------------------------------------------
    SECRET: str = "rapidly-dev-jwt-signing-key-change-in-prod"
    JWKS: JWKSFile = Field(default="./.jwks.json")
    CURRENT_JWK_KID: str = "rapidly_dev"
    WWW_AUTHENTICATE_REALM: str = "rapidly"

    # -- Sessions ----------------------------------------------------------
    USER_SESSION_TTL: timedelta = timedelta(days=31)
    USER_SESSION_MAX_PER_USER: int = 10
    USER_SESSION_COOKIE_KEY: str = "rapidly_session"
    USER_SESSION_COOKIE_DOMAIN: str = "127.0.0.1"
    CUSTOMER_SESSION_TTL: timedelta = timedelta(hours=1)
    CUSTOMER_SESSION_CODE_TTL: timedelta = timedelta(minutes=30)
    CUSTOMER_SESSION_CODE_LENGTH: int = 6
    IMPERSONATION_COOKIE_KEY: str = "rapidly_original_session"
    IMPERSONATION_INDICATOR_COOKIE_KEY: str = "rapidly_is_impersonating"

    # -- Login & verification ----------------------------------------------
    LOGIN_CODE_TTL_SECONDS: int = 60 * 10
    LOGIN_CODE_LENGTH: int = 6
    EMAIL_VERIFICATION_TTL_SECONDS: int = 60 * 30

    # -- OAuth state -------------------------------------------------------
    OAUTH_STATE_TTL: timedelta = timedelta(minutes=10)
    OAUTH_STATE_COOKIE_KEY: str = "rapidly_oauth_state"

    # -- App-store review bypass -------------------------------------------
    APP_REVIEW_EMAIL: str | None = None
    APP_REVIEW_OTP_CODE: str | None = None

    # -- CORS & hosts ------------------------------------------------------
    CORS_ORIGINS: list[str] = []
    ALLOWED_HOSTS: set[str] = {"127.0.0.1:3000", "localhost:3000"}

    # -- URLs --------------------------------------------------------------
    BASE_URL: str = "http://127.0.0.1:8000"
    ADMIN_HOST: str | None = None
    FRONTEND_BASE_URL: str = "http://127.0.0.1:3000"
    FRONTEND_DEFAULT_RETURN_PATH: str = "/"

    # -- File sharing (P2P / WebRTC) ---------------------------------------
    FILE_SHARING_CHANNEL_TTL: int = 3600
    FILE_SHARING_STUN_SERVER: str = "stun.l.google.com:19302"
    FILE_SHARING_COTURN_ENABLED: bool = False
    FILE_SHARING_TURN_HOST: str = "127.0.0.1"
    FILE_SHARING_TURN_PORT: int = 3478
    FILE_SHARING_TURN_TLS_PORT: int = 5349
    FILE_SHARING_TURN_TLS_ENABLED: bool = False
    FILE_SHARING_TURN_SECRET: str = ""
    FILE_SHARING_TURN_CREDENTIAL_TTL: int = 86400
    FILE_SHARING_PLATFORM_FEE_PERCENT: int = 500
    FILE_SHARING_MIN_PRICE_CENTS: int = 100
    FILE_SHARING_MAX_PRICE_CENTS: int = 100_000_000
    FILE_SHARING_PAID_CHANNEL_TTL: int = 86400

    # -- ClamAV (malware scanning) -----------------------------------------
    CLAMAV_ENABLED: bool = False
    CLAMAV_SOCKET_PATH: str | None = "/var/run/clamav/clamd.sock"
    CLAMAV_HOST: str = "localhost"
    CLAMAV_PORT: int = 3310
    CLAMAV_QUARANTINE_BUCKET: str = "rapidly-quarantine"
    CLAMAV_MAX_SCAN_SIZE_BYTES: int = 500 * 1024 * 1024  # 500 MB

    # -- Payments (Stripe) -------------------------------------------------
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_CONNECT_WEBHOOK_SECRET: str = ""

    # -- Email delivery ----------------------------------------------------
    EMAIL_RENDERER_BINARY_PATH: Annotated[
        Path, AfterValidator(_validate_email_renderer_binary_path)
    ] = (
        Path(__file__).parent.parent
        / "emails"
        / "bin"
        / f"react-email-pkg{_binary_ext}"
    )
    EMAIL_SENDER: EmailSender = EmailSender.logger
    GMAIL_EMAIL: str = ""
    GMAIL_APP_PASSWORD: str = ""
    GMAIL_SMTP_HOST: str = "smtp.gmail.com"
    GMAIL_SMTP_PORT: int = 587
    EMAIL_FROM_NAME: str = "Rapidly"
    EMAIL_FROM_DOMAIN: str = "notifications.rapidly.tech"
    EMAIL_FROM_LOCAL: str = "mail"
    EMAIL_DEFAULT_REPLY_TO_NAME: str = "Rapidly Support"
    EMAIL_DEFAULT_REPLY_TO_EMAIL_ADDRESS: str = "support@rapidly.tech"

    # -- OAuth providers ---------------------------------------------------
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT: str = "common"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    DISCORD_CLIENT_ID: str = ""
    DISCORD_CLIENT_SECRET: str = ""
    DISCORD_BOT_TOKEN: str = ""
    DISCORD_BOT_PERMISSIONS: str = "268435459"
    DISCORD_PROXY_URL: str = ""
    APPLE_CLIENT_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_KEY_VALUE: str = ""

    # -- AI ----------------------------------------------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "o4-mini-2025-04-16"

    # -- Background workers ------------------------------------------------
    WORKER_HEALTH_CHECK_INTERVAL: timedelta = timedelta(seconds=30)
    WORKER_MAX_RETRIES: int = 20
    WORKER_RETRY_BASE_DELAY_MS: int = 2_000
    WORKER_PROMETHEUS_DIR: Path = Path(tempfile.gettempdir()) / "prometheus_multiproc"
    WORKER_DEFAULT_DEBOUNCE_MIN_THRESHOLD: timedelta = timedelta(seconds=15)
    WORKER_DEFAULT_DEBOUNCE_MAX_THRESHOLD: timedelta = timedelta(minutes=15)

    # -- Webhooks ----------------------------------------------------------
    WEBHOOK_MAX_RETRIES: int = 10
    WEBHOOK_EVENT_RETENTION_PERIOD: timedelta = timedelta(days=30)
    WEBHOOK_FAILURE_THRESHOLD: int = 10

    # -- Observability (Sentry) --------------------------------------------
    SENTRY_DSN: str | None = None

    # -- Observability (Logfire) -------------------------------------------
    LOGFIRE_TOKEN: str | None = None
    LOGFIRE_IGNORED_ACTORS: set[str] = {
        "workspace_access_token.record_usage",
    }

    # -- Observability (PostHog) -------------------------------------------
    POSTHOG_PROJECT_API_KEY: str = ""
    POSTHOG_DEBUG: bool = False

    # -- Observability (Prometheus remote-write) ---------------------------
    PROMETHEUS_REMOTE_WRITE_URL: str | None = None
    PROMETHEUS_REMOTE_WRITE_USERNAME: str | None = None
    PROMETHEUS_REMOTE_WRITE_PASSWORD: str | None = None
    PROMETHEUS_REMOTE_WRITE_INTERVAL: Annotated[int, Ge(1)] = 15

    # -- Observability (Tinybird event analytics) --------------------------
    TINYBIRD_API_URL: str = "http://localhost:7181"
    TINYBIRD_API_TOKEN: str | None = None
    TINYBIRD_CLICKHOUSE_URL: str = "http://localhost:7182"
    TINYBIRD_CLICKHOUSE_USERNAME: str = "default"
    TINYBIRD_CLICKHOUSE_TOKEN: str | None = None
    TINYBIRD_WORKSPACE: str | None = None
    TINYBIRD_EVENTS_WRITE: bool = False
    TINYBIRD_EVENTS_READ: bool = False

    # -- Brand & assets ----------------------------------------------------
    FAVICON_URL: str = "https://raw.githubusercontent.com/rapidly-tech/rapidly/2648cf7472b5128704a097cd1eb3ae5f1dd847e5/docs/docs/assets/favicon.png"
    THUMBNAIL_URL: str = "https://raw.githubusercontent.com/rapidly-tech/rapidly/4fd899222e200ca70982f437039f549b7a822ecc/clients/apps/web/public/email-logo-dark.png"

    # -- Logo.dev (company avatar resolution) ------------------------------
    LOGO_DEV_PUBLISHABLE_KEY: str | None = None
    PERSONAL_EMAIL_DOMAINS: set[str] = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "aol.com",
        "icloud.com",
        "mail.com",
        "protonmail.com",
        "zoho.com",
        "gmx.com",
        "yandex.com",
        "msn.com",
        "live.com",
        "qq.com",
    }

    # -- Pagination --------------------------------------------------------
    API_PAGINATION_MAX_LIMIT: int = 100

    # -- Reserved slugs ----------------------------------------------------
    WORKSPACE_SLUG_RESERVED_KEYWORDS: list[str] = [
        "dashboard",
        "settings",
        "login",
        "signup",
        "oauth2",
        "admin",
        "finance",
        "docs",
        "careers",
        "legal",
        ".well-known",
        "file-sharing",
        "download",
        "share",
    ]

    # -- Runtime -----------------------------------------------------------
    ENV: Environment = Environment.development
    SQLALCHEMY_DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    TESTING: bool = False

    # ======================================================================
    # Sub-group accessors
    # ======================================================================

    @property
    def db(self) -> _DatabaseCfg:
        """Structured view of all database-related settings."""
        return _DatabaseCfg(
            user=self.POSTGRES_USER,
            pwd=self.POSTGRES_PWD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DATABASE,
            pool_size=self.DATABASE_POOL_SIZE,
            sync_pool_size=self.DATABASE_SYNC_POOL_SIZE,
            pool_recycle_seconds=self.DATABASE_POOL_RECYCLE_SECONDS,
            command_timeout_seconds=self.DATABASE_COMMAND_TIMEOUT_SECONDS,
            stream_yield_per=self.DATABASE_STREAM_YIELD_PER,
            read_user=self.POSTGRES_READ_USER,
            read_pwd=self.POSTGRES_READ_PWD,
            read_host=self.POSTGRES_READ_HOST,
            read_port=self.POSTGRES_READ_PORT,
            read_database=self.POSTGRES_READ_DATABASE,
        )

    @property
    def cache(self) -> _CacheCfg:
        """Structured view of Redis settings."""
        return _CacheCfg(
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            db=self.REDIS_DB,
            password=self.REDIS_PASSWORD,
        )

    @property
    def file_sharing(self) -> _FileSharingCfg:
        """Structured view of WebRTC file-sharing settings."""
        return _FileSharingCfg(
            channel_ttl=self.FILE_SHARING_CHANNEL_TTL,
            stun_server=self.FILE_SHARING_STUN_SERVER,
            coturn_enabled=self.FILE_SHARING_COTURN_ENABLED,
            turn_host=self.FILE_SHARING_TURN_HOST,
            turn_port=self.FILE_SHARING_TURN_PORT,
            turn_tls_port=self.FILE_SHARING_TURN_TLS_PORT,
            turn_tls_enabled=self.FILE_SHARING_TURN_TLS_ENABLED,
            turn_secret=self.FILE_SHARING_TURN_SECRET,
            turn_credential_ttl=self.FILE_SHARING_TURN_CREDENTIAL_TTL,
            platform_fee_percent=self.FILE_SHARING_PLATFORM_FEE_PERCENT,
            min_price_cents=self.FILE_SHARING_MIN_PRICE_CENTS,
            max_price_cents=self.FILE_SHARING_MAX_PRICE_CENTS,
            paid_channel_ttl=self.FILE_SHARING_PAID_CHANNEL_TTL,
        )

    @property
    def clamav(self) -> _ClamAVCfg:
        """Structured view of ClamAV settings."""
        return _ClamAVCfg(
            enabled=self.CLAMAV_ENABLED,
            socket_path=self.CLAMAV_SOCKET_PATH,
            host=self.CLAMAV_HOST,
            port=self.CLAMAV_PORT,
            quarantine_bucket=self.CLAMAV_QUARANTINE_BUCKET,
        )

    # ======================================================================
    # Derived properties (flat, kept for backwards compatibility)
    # ======================================================================

    @property
    def redis_url(self) -> str:
        """Assemble a ``redis://`` URI from host, port, and DB index."""
        return self.cache.url

    def get_postgres_dsn(self, driver: Literal["asyncpg", "psycopg2"]) -> str:
        """Construct the primary-database connection string for *driver*."""
        return self.db.dsn(driver)

    def is_read_replica_configured(self) -> bool:
        """Return whether every read-replica connection parameter has been set."""
        return self.db.has_read_replica

    def get_postgres_read_dsn(
        self, driver: Literal["asyncpg", "psycopg2"]
    ) -> str | None:
        """Construct the read-replica connection string, returning ``None`` when unconfigured."""
        return self.db.read_dsn(driver)

    # ======================================================================
    # Environment predicates
    # ======================================================================

    def is_environment(self, environments: set[Environment]) -> bool:
        """Return ``True`` if the current ``ENV`` belongs to the given set."""
        return self.ENV in environments

    def is_development(self) -> bool:
        return self.ENV is Environment.development

    def is_testing(self) -> bool:
        return self.ENV is Environment.testing

    def is_sandbox(self) -> bool:
        return self.ENV is Environment.sandbox

    def is_production(self) -> bool:
        return self.ENV is Environment.production

    # ======================================================================
    # URL builders
    # ======================================================================

    def generate_external_url(self, path: str) -> str:
        """Produce a fully-qualified URL routed to the backend server."""
        return f"{self.BASE_URL}{path}"

    def generate_frontend_url(self, path: str) -> str:
        """Produce a fully-qualified URL routed to the Next.js client app."""
        return f"{self.FRONTEND_BASE_URL}{path}"

    def generate_admin_url(self, path: str) -> str:
        """Produce an admin URL, using the dedicated host when one is configured."""
        if self.ADMIN_HOST is None:
            return self.generate_external_url(f"/admin{path}")
        return f"https://{self.ADMIN_HOST}{path}"

    # ======================================================================
    # Stripe helpers
    # ======================================================================

    # ======================================================================
    # Validators
    # ======================================================================

    @model_validator(mode="after")
    def _enforce_file_sharing_invariants(self) -> Settings:
        """Validate inter-dependent file-sharing settings in one pass."""
        if self.FILE_SHARING_COTURN_ENABLED and not self.FILE_SHARING_TURN_SECRET:
            raise ValueError(
                "FILE_SHARING_TURN_SECRET must be set when FILE_SHARING_COTURN_ENABLED is True"
            )
        if self.FILE_SHARING_MIN_PRICE_CENTS >= self.FILE_SHARING_MAX_PRICE_CENTS:
            raise ValueError(
                "FILE_SHARING_MIN_PRICE_CENTS must be less than FILE_SHARING_MAX_PRICE_CENTS"
            )
        return self

    @model_validator(mode="after")
    def _reject_default_secrets_in_production(self) -> Settings:
        """Refuse to start in production/sandbox with insecure default secrets."""
        if self.ENV not in (
            Environment.production,
            Environment.sandbox,
            Environment.test,
        ):
            return self

        _defaults: dict[str, str] = {
            "SECRET": "rapidly-dev-jwt-signing-key-change-in-prod",
            "AWS_ACCESS_KEY_ID": "rapidly-development",
            "AWS_SECRET_ACCESS_KEY": "rapidly123456789",
            "MINIO_PWD": "rapidlyrapidly",
        }
        insecure = [
            name
            for name, default in _defaults.items()
            if getattr(self, name) == default
        ]
        if insecure:
            raise ValueError(
                f"Insecure default values detected for {', '.join(insecure)}. "
                f"These must be changed before running in {self.ENV} mode."
            )

        if self.STRIPE_SECRET_KEY and not self.STRIPE_WEBHOOK_SECRET:
            raise ValueError(
                "STRIPE_WEBHOOK_SECRET must be set when STRIPE_SECRET_KEY is configured."
            )
        if self.STRIPE_SECRET_KEY and not self.STRIPE_CONNECT_WEBHOOK_SECRET:
            raise ValueError(
                "STRIPE_CONNECT_WEBHOOK_SECRET must be set when STRIPE_SECRET_KEY is configured."
            )
        return self


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

settings = Settings()
