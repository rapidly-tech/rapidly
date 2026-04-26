"""Pydantic schemas for file sharing channel, ICE, and secret sharing operations."""

from datetime import datetime

from pydantic import UUID4, Field, field_validator

from rapidly.config import settings
from rapidly.core.currency import PresentmentCurrency
from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.file_share_payment import FileSharePaymentStatus
from rapidly.models.file_share_report import FileShareReportStatus
from rapidly.models.file_share_session import FileShareSessionStatus

# ── Shared Validators ──


def _validate_price_cents(v: int | None) -> int | None:
    """Shared price validation for secrets and channels."""
    if v is not None and v > 0:
        if v < settings.FILE_SHARING_MIN_PRICE_CENTS:
            raise ValueError(
                f"Minimum price is {settings.FILE_SHARING_MIN_PRICE_CENTS} cents"
            )
        if v > settings.FILE_SHARING_MAX_PRICE_CENTS:
            raise ValueError(
                f"Maximum price is {settings.FILE_SHARING_MAX_PRICE_CENTS} cents"
            )
    return v


# ── Request Schemas ──


class SecretCreateRequest(Schema):
    """Request schema for creating a new secret (text)."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=1 * 1024 * 1024,  # 1MB limit for encrypted payload
        description="OpenPGP encrypted secret message",
    )
    expiration: int = Field(
        default=3600,
        ge=60,
        le=604800,
        description="Secret expiration time in seconds (60=1min .. 604800=1w)",
    )
    workspace_id: UUID4 | None = Field(
        default=None,
        description="Workspace ID to associate the secret with (for workspace-scoped counters)",
    )
    price_cents: int | None = Field(
        default=None,
        ge=0,
        description="Price in cents (None = free)",
    )
    currency: PresentmentCurrency | None = Field(
        default=None,
        description=(
            "ISO 4217 currency code. When omitted, the workspace's default "
            "presentment currency is used (falls back to ``usd`` if no "
            "workspace is provided)."
        ),
    )
    title: str | None = Field(
        default=None,
        max_length=255,
        description="Display title for paid storefront listing",
    )

    @field_validator("price_cents")
    @classmethod
    def validate_price(cls, v: int | None) -> int | None:
        return _validate_price_cents(v)


class FileSecretCreateRequest(SecretCreateRequest):
    """Request schema for creating a new file secret.

    Identical to SecretCreateRequest.  Kept as a separate class so that the
    OpenAPI spec documents distinct request bodies for ``/secret`` vs ``/file``
    endpoints, making it easier to add file-specific constraints later.
    """

    pass


# ── Response Schemas ──


class FileShareStatsResponse(Schema):
    """Public stats for the landing page counter."""

    total_shares: int = Field(..., description="Total number of file shares created")


class SecretCreateResponse(Schema):
    """Response schema for secret/file creation.

    Note: The ``message`` field here contains a UUID identifier (not the
    encrypted content).  This reuses the field name from the request schema
    for wire-format compatibility.
    """

    message: str = Field(..., description="UUID identifier for the stored secret")


class SecretMetadataResponse(Schema):
    """Response schema for peeking at secret metadata without consuming it."""

    title: str | None = Field(default=None, description="Display title")
    payment_required: bool = Field(
        default=False,
        description="Whether payment is required before content is accessible",
    )
    price_cents: int | None = Field(
        default=None, description="Price in cents (None = free)"
    )
    currency: str | None = Field(default=None, description="ISO 4217 currency code")


class SecretFetchResponse(Schema):
    """Response schema for fetching a secret."""

    message: str = Field(..., description="OpenPGP encrypted message/file")
    payment_required: bool = Field(
        default=False,
        description="Whether payment is required before content is accessible",
    )
    price_cents: int | None = Field(
        default=None, description="Price in cents (None = free)"
    )
    currency: str | None = Field(default=None, description="ISO 4217 currency code")
    title: str | None = Field(default=None, description="Display title")


class ChannelCreateRequest(Schema):
    """Request schema for creating a new channel."""

    max_downloads: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="Maximum number of downloads (0 = unlimited)",
    )
    price_cents: int | None = Field(
        default=None,
        ge=0,
        description="Price in cents (None = free)",
    )
    currency: PresentmentCurrency | None = Field(
        default=None,
        description=(
            "ISO 4217 currency code. When omitted, the workspace's default "
            "presentment currency is used (falls back to ``usd`` if no "
            "workspace is provided)."
        ),
    )
    title: str | None = Field(
        default=None,
        max_length=255,
        description="Custom display title for the share (shown in dashboard)",
    )
    file_name: str | None = Field(
        default=None,
        max_length=255,
        description="Display name for buyer",
    )
    file_size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Display size for buyer",
    )
    workspace_id: UUID4 | None = Field(
        default=None,
        description="Workspace ID for Stripe account lookup (required for paid channels)",
    )

    @field_validator("price_cents")
    @classmethod
    def validate_price(cls, v: int | None) -> int | None:
        return _validate_price_cents(v)


class ChannelCreateResponse(Schema):
    """Response schema for channel creation."""

    secret: str = Field(..., description="Channel ownership secret")
    long_slug: str = Field(..., description="Human-readable slug")
    short_slug: str = Field(..., description="Short alphanumeric slug")


class ChannelRenewRequest(Schema):
    """Request schema for renewing a channel's TTL."""

    secret: str = Field(
        ..., min_length=1, max_length=128, description="Channel ownership secret"
    )


class ChannelRenewResponse(Schema):
    """Response schema for channel renewal."""

    success: bool = Field(..., description="Whether the renewal was successful")


class ChannelDestroyRequest(Schema):
    """Request schema for destroying a channel."""

    secret: str = Field(
        ..., min_length=1, max_length=128, description="Channel ownership secret"
    )


class ChannelDestroyResponse(Schema):
    """Response schema for channel destruction."""

    success: bool = Field(
        ...,
        description="Whether the destruction request was authenticated and processed",
    )
    immediate: bool = Field(
        default=False,
        description="True if destruction happened immediately (confirmed), False if pending",
    )
    message: str = Field(
        default="",
        description="Human-readable description of the destruction status",
    )


class PasswordAttemptRequest(Schema):
    """Request schema for recording a password attempt."""

    secret: str = Field(
        ..., min_length=1, max_length=128, description="Channel ownership secret"
    )


class PasswordAttemptResponse(Schema):
    """Response schema for password attempt tracking."""

    allowed: bool = Field(
        ...,
        description="Whether the attempt is allowed (not rate-limited or locked out)",
    )


class ReaderTokenRequest(Schema):
    """Request schema for registering a reader authorization token."""

    secret: str = Field(
        ..., min_length=1, max_length=128, description="Channel ownership secret"
    )
    token_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
        description="SHA-256 hash of the reader token",
    )


class ReaderTokenResponse(Schema):
    """Response schema for reader token registration."""

    success: bool = Field(..., description="Whether the token was registered")


class ChannelFetchResponse(Schema):
    """Response schema for fetching channel info (download page)."""

    available: bool = Field(
        default=True, description="Whether the channel is available for download"
    )
    title: str | None = Field(
        default=None, description="Custom display title set by the uploader"
    )
    price_cents: int | None = Field(
        default=None, description="Price in cents (None = free)"
    )
    currency: str | None = Field(default=None, description="ISO 4217 currency code")
    file_name: str | None = Field(default=None, description="Display name for buyer")
    file_size_bytes: int | None = Field(
        default=None, description="Display size for buyer"
    )
    payment_required: bool = Field(
        default=False,
        description="Whether payment is required (False if free or already paid)",
    )
    creator_country: str = Field(
        default="",
        description="ISO 3166-1 alpha-2 country code of the uploader",
    )


class ReportRequest(Schema):
    """Request schema for reporting a channel violation."""

    token: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Reader token to authenticate the reporter",
    )


class ReportResponse(Schema):
    """Response schema for channel report."""

    success: bool = Field(..., description="Whether the report was processed")


class DownloadCompleteRequest(Schema):
    """Request schema for recording a completed download."""

    token: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Reader token to authenticate the downloader",
    )


class DownloadCompleteResponse(Schema):
    """Response schema for download completion."""

    success: bool = Field(..., description="Whether the completion was recorded")
    remaining: int = Field(
        ..., description="Downloads remaining (0 = limit reached, -1 = unlimited)"
    )


class ICEConfigRequest(Schema):
    """Request schema for fetching ICE server configuration."""

    token: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Reader token to authenticate the requester",
    )


# ── ICE Schemas ──


class ICEServer(Schema):
    """ICE server configuration."""

    urls: str | list[str] = Field(..., description="STUN/TURN server URL(s)")
    username: str | None = Field(
        None, description="TURN username (for authenticated servers)"
    )
    credential: str | None = Field(
        None, description="TURN credential (for authenticated servers)"
    )


class ICEConfigResponse(Schema):
    """Response schema for ICE configuration."""

    ice_servers: list[ICEServer] = Field(..., description="List of ICE servers")


class ChannelCheckoutResponse(Schema):
    """Response schema for creating a checkout session for a paid channel."""

    checkout_url: str = Field(..., description="Stripe Checkout URL to redirect buyer")
    session_id: str = Field(..., description="Stripe Checkout Session ID")


class DirectPaymentResponse(Schema):
    """Response when paying with a saved payment method (no Stripe Checkout redirect)."""

    client_secret: str = Field(
        description="PaymentIntent client_secret for frontend confirmation"
    )
    payment_intent_id: str = Field(description="Stripe PaymentIntent ID")
    requires_action: bool = Field(
        default=False,
        description="True if 3D Secure verification is needed",
    )


class ChannelCheckoutRequest(Schema):
    """Request body for channel checkout (optional saved payment method)."""

    payment_method_id: UUID4 | None = Field(
        default=None,
        description="ID of a saved payment method to charge directly (skips Stripe Checkout)",
    )


class ClaimPaymentTokenRequest(Schema):
    """Request to exchange a Stripe checkout session ID for the payment token."""

    checkout_session_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stripe Checkout Session ID from the success redirect",
    )


class SecretCheckoutResponse(Schema):
    """Response schema for creating a checkout session for a paid secret."""

    checkout_url: str = Field(..., description="Stripe Checkout URL to redirect buyer")
    session_id: str = Field(..., description="Stripe Checkout Session ID")


# ── Internal Models ──


class FileShareSessionSchema(AuditableSchema, IdentifiableSchema):
    """Read schema for a file share session audit record."""

    short_slug: str
    long_slug: str
    status: FileShareSessionStatus
    max_downloads: int
    download_count: int
    price_cents: int | None
    currency: str
    title: str | None
    file_name: str | None
    file_size_bytes: int | None
    ttl_seconds: int | None
    expires_at: datetime | None
    activated_at: datetime | None
    completed_at: datetime | None
    user_id: UUID4 | None
    workspace_id: UUID4 | None
    share_id: UUID4 | None


class FileShareDownloadSchema(AuditableSchema, IdentifiableSchema):
    """Read schema for a file share download audit record."""

    session_id: UUID4
    slot_number: int


class FileSharePaymentSchema(AuditableSchema, IdentifiableSchema):
    """Read schema for a file share payment audit record."""

    session_id: UUID4
    status: FileSharePaymentStatus
    amount_cents: int
    currency: str
    platform_fee_cents: int
    stripe_checkout_session_id: str | None
    stripe_payment_intent_id: str | None
    buyer_email: str | None
    buyer_name: str | None


class FileShareReportSchema(AuditableSchema, IdentifiableSchema):
    """Read schema for a file share report audit record."""

    session_id: UUID4
    status: FileShareReportStatus
    reason: str | None
    reviewed_at: datetime | None


class FileShareSessionDetailSchema(FileShareSessionSchema):
    """Detailed session schema including payments, downloads, and reports."""

    payments: list[FileSharePaymentSchema] = []
    downloads: list[FileShareDownloadSchema] = []
    reports: list[FileShareReportSchema] = []


class ChecksumUploadRequest(Schema):
    """Request schema for uploading file checksums."""

    secret: str = Field(
        ..., min_length=1, max_length=128, description="Channel ownership secret"
    )
    checksums: dict[str, str] = Field(
        ...,
        description="Map of fileName to SHA-256 hex digest",
    )

    @field_validator("checksums")
    @classmethod
    def validate_checksums(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 1000:
            raise ValueError("Too many checksum entries (max 1000)")
        for filename, digest in v.items():
            if len(filename) > 255:
                raise ValueError(f"Filename too long: {len(filename)}")
            if len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest):
                raise ValueError(f"Invalid SHA-256 digest for {filename}")
        return v


class ChecksumUploadResponse(Schema):
    """Response schema for checksum upload."""

    success: bool = Field(..., description="Whether checksums were stored")


class ChecksumFetchResponse(Schema):
    """Response schema for fetching checksums."""

    checksums: dict[str, str] = Field(
        ..., description="Map of fileName to SHA-256 hex digest"
    )


class ReportUpdateRequest(Schema):
    """Request schema for updating a report status."""

    status: FileShareReportStatus | None = Field(
        default=None,
        description="New report status (reviewed, dismissed, or actioned)",
    )
    admin_notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional admin notes about the review decision",
    )
