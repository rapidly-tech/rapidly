"""ORM model for peer-to-peer file sharing sessions."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from rapidly.core.db.models.base import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StringEnum

if TYPE_CHECKING:
    from .share import Share
    from .user import User
    from .workspace import Workspace


class FileShareSessionStatus(StrEnum):
    created = "created"
    active = "active"
    completed = "completed"
    expired = "expired"
    destroyed = "destroyed"
    reported = "reported"


class FileShareSession(BaseEntity):
    """Represents an active file-sharing session with optional pricing."""

    __tablename__ = "file_share_sessions"
    __table_args__ = (
        Index("ix_file_share_sessions_short_slug", "short_slug", unique=True),
        Index("ix_file_share_sessions_long_slug", "long_slug", unique=True),
        Index("ix_file_share_sessions_user_id", "user_id"),
        Index("ix_file_share_sessions_workspace_id", "workspace_id"),
        Index("ix_file_share_sessions_status", "status"),
        Index("ix_file_share_sessions_expires_at", "expires_at"),
    )

    short_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    long_slug: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[FileShareSessionStatus] = mapped_column(
        StringEnum(FileShareSessionStatus),
        nullable=False,
        default=FileShareSessionStatus.created,
    )

    max_downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    ttl_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    creator_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Nullable FKs
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    share_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("shares.id", ondelete="SET NULL"), nullable=True
    )

    @declared_attr
    def user(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")

    @declared_attr
    def workspace(cls) -> Mapped["Workspace | None"]:
        return relationship("Workspace", lazy="raise")

    @declared_attr
    def share(cls) -> Mapped["Share | None"]:
        return relationship("Share", lazy="raise")
