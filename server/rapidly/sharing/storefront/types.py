"""Pydantic schemas for public storefront responses."""

from datetime import datetime

from pydantic import Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.platform.workspace.types import Workspace


class FileShareStorefront(AuditableSchema, IdentifiableSchema):
    """Schema of a public paid file share on the storefront."""

    short_slug: str = Field(description="Short slug for the file share link.")
    title: str | None = Field(default=None, description="Title of the file share.")
    file_name: str | None = Field(default=None, description="Original file name.")
    file_size_bytes: int | None = Field(default=None, description="File size in bytes.")
    price_cents: int | None = Field(default=None, description="Price in cents.")
    currency: str = Field(default="usd", description="Currency code (e.g. usd).")
    download_count: int = Field(default=0, description="Number of completed downloads.")
    expires_at: datetime | None = Field(
        default=None, description="Expiration timestamp, if set."
    )


class SecretStorefront(Schema):
    """Schema of a public paid secret on the storefront."""

    id: str = Field(description="Secret UUID identifier.")
    created_at: datetime = Field(description="Creation timestamp.")
    uuid: str = Field(description="Secret UUID for access URLs.")
    title: str | None = Field(default=None, description="Display title.")
    price_cents: int | None = Field(default=None, description="Price in cents.")
    currency: str = Field(default="usd", description="Currency code (e.g. usd).")
    expires_at: datetime | None = Field(
        default=None, description="Expiration timestamp, if set."
    )


class StorefrontCustomer(Schema):
    name: str


class StorefrontCustomers(Schema):
    total: int
    customers: list[StorefrontCustomer]


class Storefront(Schema):
    """Schema of a public storefront."""

    workspace: Workspace
    file_shares: list[FileShareStorefront]
    secrets: list[SecretStorefront] = Field(default_factory=list)
    customers: StorefrontCustomers
