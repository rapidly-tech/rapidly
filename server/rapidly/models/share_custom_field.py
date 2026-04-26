"""Junction table linking custom fields to products.

Each row attaches a ``CustomField`` to a ``Share`` with ordering
and requiredness metadata, managed via the shared
``AttachedCustomFieldMixin``.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.catalog.custom_field.attachment import AttachedCustomFieldMixin
from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from rapidly.models import Share


class ShareCustomField(AttachedCustomFieldMixin, BaseEntity):
    """Associates a custom field with a share at a specific display order."""

    __tablename__ = "share_custom_fields"
    __table_args__ = (UniqueConstraint("share_id", "order"),)

    # -- Share association -------------------------------------------------

    share_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("shares.id", ondelete="cascade"),
        primary_key=True,
    )

    @declared_attr
    def share(cls) -> Mapped["Share"]:
        return relationship(
            "Share", lazy="raise", back_populates="attached_custom_fields"
        )
