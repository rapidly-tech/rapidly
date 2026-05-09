"""ORM model for abuse reports filed against file sharing sessions."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from rapidly.core.db.models.base import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StringEnum

if TYPE_CHECKING:
    from .file_share_session import FileShareSession


class FileShareReportStatus(StrEnum):
    pending = "pending"
    reviewed = "reviewed"
    dismissed = "dismissed"
    actioned = "actioned"


class FileShareReport(BaseEntity):
    """Stores an abuse report submitted against a shared file."""

    __tablename__ = "file_share_reports"

    session_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("file_share_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[FileShareReportStatus] = mapped_column(
        StringEnum(FileShareReportStatus),
        nullable=False,
        default=FileShareReportStatus.pending,
    )
    reporter_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    @declared_attr
    def session(cls) -> Mapped["FileShareSession"]:
        return relationship("FileShareSession", lazy="raise")
