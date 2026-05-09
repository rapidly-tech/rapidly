"""Association between a share and its media files.

Each row represents one image or video attached to a share listing,
with an ``order`` column controlling the display sequence.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from rapidly.models import Share
    from rapidly.models.file import ShareMediaFile


class ShareMedia(BaseEntity):
    """Links a media file to a share with explicit ordering.

    This is an association table with a composite primary key of
    (share_id, file_id).  The unique constraint on (share_id, order)
    ensures no two attachments share the same display position.
    """

    __tablename__ = "share_medias"
    __table_args__ = (UniqueConstraint("share_id", "order"),)

    # -- Composite primary key -----------------------------------------------

    share_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("shares.id", ondelete="cascade"),
        primary_key=True,
    )
    file_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("files.id", ondelete="cascade"),
        primary_key=True,
    )

    # -- Display order -------------------------------------------------------

    order: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    # -- Relationships -------------------------------------------------------

    @declared_attr
    def share(cls) -> Mapped["Share"]:
        return relationship("Share", lazy="raise", back_populates="share_medias")

    @declared_attr
    def file(cls) -> Mapped["ShareMediaFile"]:
        # Eager-load the file since this is an association table
        return relationship("ShareMediaFile", lazy="joined")
