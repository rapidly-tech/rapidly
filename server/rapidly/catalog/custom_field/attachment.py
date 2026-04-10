"""Helpers for attaching and detaching custom field values on resources.

Provides the ``AttachedCustomFieldMixin`` for SQLAlchemy models that
participate in custom-field associations, and automatically tracks every
concrete subclass via a SQLAlchemy mapper event.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Uuid, event
from sqlalchemy.orm import (
    Mapped,
    Mapper,
    declared_attr,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    from rapidly.models import CustomField


class AttachedCustomFieldMixin:
    """Mixin for association models that link a resource to a custom field.

    Concrete subclasses must define the additional foreign-key column
    pointing at the owning resource (e.g. ``share_id``).
    """

    custom_field_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("custom_fields.id", ondelete="cascade"),
        primary_key=True,
    )
    order: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @declared_attr
    def custom_field(cls) -> Mapped[CustomField]:
        # Association tables benefit from eager loading of the related field.
        return relationship("CustomField", lazy="joined")


# Global registry of every concrete model that uses the mixin.
attached_custom_fields_models: set[type[AttachedCustomFieldMixin]] = set()


@event.listens_for(Mapper, "mapper_configured")
def _track_attached_custom_field_model(_mapper: Mapper[Any], class_: type) -> None:
    """Auto-register subclasses of ``AttachedCustomFieldMixin``."""
    if issubclass(class_, AttachedCustomFieldMixin):
        attached_custom_fields_models.add(class_)
