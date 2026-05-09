"""ORM model for file share download events."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .file_share_session import FileShareSession


class FileShareDownload(BaseEntity):
    """Records a download event for a shared file."""

    __tablename__ = "file_share_downloads"

    session_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("file_share_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    downloader_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)

    @declared_attr
    def session(cls) -> Mapped["FileShareSession"]:
        return relationship("FileShareSession", lazy="raise")
