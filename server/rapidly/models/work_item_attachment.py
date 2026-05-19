"""Association between a work item and an uploaded file.

``WorkItemAttachment`` is a thin join row that points a work item at
an existing ``File`` (uploaded through the catalog/file endpoints) plus
who uploaded it.  Reusing the existing polymorphic File model keeps
malware scanning, presign-URL generation, and bucket selection out of
this submodule's concern — attachments inherit them for free.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .file import File
    from .user import User
    from .work_item import WorkItem


class WorkItemAttachment(BaseEntity):
    """A file attached to a work item."""

    __tablename__ = "work_item_attachments"
    __table_args__ = (
        UniqueConstraint(
            "work_item_id",
            "file_id",
            name="work_item_attachments_work_item_id_file_id_key",
        ),
    )

    work_item_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    file_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("files.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    uploaded_by_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")

    @declared_attr
    def file(cls) -> Mapped["File"]:
        # Eager-load so list responses can include file metadata without
        # an N+1 lazy-load on each row.
        return relationship("File", lazy="joined")

    @declared_attr
    def uploaded_by(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
