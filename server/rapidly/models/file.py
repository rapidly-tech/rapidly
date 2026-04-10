"""Polymorphic file model with malware scanning support.

Uses SQLAlchemy single-table inheritance keyed on ``service`` to
distinguish downloadable files, share media, and workspace avatars.
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    ForeignKey,
    String,
    Uuid,
)
from sqlalchemy.orm import (
    Mapped,
    declared_attr,
    mapped_column,
    relationship,
)

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from rapidly.models import (
        Workspace,
    )


# ── Discriminator enum ────────────────────────────────────────────────


class FileServiceTypes(StrEnum):
    """Discriminator values for the polymorphic ``File`` hierarchy."""

    downloadable = "downloadable"
    product_media = "product_media"
    workspace_avatar = "workspace_avatar"


# ── Scan lifecycle ────────────────────────────────────────────────────


class FileScanStatus(StrEnum):
    """ClamAV scan lifecycle states."""

    pending = "pending"
    scanning = "scanning"
    clean = "clean"
    infected = "infected"
    mime_mismatch = "mime_mismatch"
    error = "error"
    skipped = "skipped"


# Statuses that allow the file to be served to end-users.
SCAN_SAFE_STATUSES: frozenset[FileScanStatus] = frozenset(
    {FileScanStatus.clean, FileScanStatus.skipped}
)


# ── Base file model ───────────────────────────────────────────────────


class File(BaseEntity):
    """S3-backed file record with integrity checksums and malware scanning."""

    __tablename__ = "files"

    # ── Ownership ──────────────────────────────────────────────────────

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    # ── File metadata ──────────────────────────────────────────────────

    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str | None] = mapped_column(String, nullable=True)
    path: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    service: Mapped[FileServiceTypes] = mapped_column(String, nullable=False)

    last_modified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # ── Integrity checksums ────────────────────────────────────────────

    storage_version: Mapped[str | None] = mapped_column(String, nullable=True)
    checksum_etag: Mapped[str | None] = mapped_column(String, nullable=True)
    checksum_sha256_base64: Mapped[str | None] = mapped_column(String, nullable=True)
    checksum_sha256_hex: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Availability flags ─────────────────────────────────────────────

    is_uploaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Malware scanning ───────────────────────────────────────────────

    scan_status: Mapped[FileScanStatus | None] = mapped_column(
        String, nullable=True, default=None, index=True
    )
    scan_result: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    scanned_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )

    @property
    def is_scan_safe(self) -> bool:
        """True when the file has passed malware scanning (or scanning was skipped)."""
        return self.scan_status in SCAN_SAFE_STATUSES

    __mapper_args__ = {
        "polymorphic_on": "service",
    }


# ── Polymorphic subtypes ──────────────────────────────────────────────


class DownloadableFile(File):
    """User-downloadable deliverable file."""

    __mapper_args__ = {
        "polymorphic_identity": FileServiceTypes.downloadable,
    }


class ShareMediaFile(File):
    """Image or video attached to a share listing."""

    __mapper_args__ = {
        "polymorphic_identity": FileServiceTypes.product_media,
    }


class WorkspaceAvatarFile(File):
    """Avatar image for an workspace profile."""

    __mapper_args__ = {
        "polymorphic_identity": FileServiceTypes.workspace_avatar,
    }
