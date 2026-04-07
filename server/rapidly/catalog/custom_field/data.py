"""Custom-field data access: value resolution and dynamic model generation.

Builds runtime Pydantic models from custom-field definitions so that
checkout forms and API responses can validate and present field values
with the correct types and constraints.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Mapper, ORMDescriptor, mapped_column

if TYPE_CHECKING:
    from rapidly.models import Workspace


# ── Value type shared across all custom-field storage ────────────────

CustomFieldValue = str | int | bool | datetime.datetime | None


# ── SQLAlchemy mixin ─────────────────────────────────────────────────


class CustomFieldDataMixin:
    """Adds a ``custom_field_data`` JSONB column to a SQLAlchemy model."""

    custom_field_data: Mapped[dict[str, CustomFieldValue]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # Type-checker hint — concrete models must declare their own
    # ``workspace`` relationship.
    if TYPE_CHECKING:
        workspace: ORMDescriptor[Workspace]


# Auto-tracking registry for every model that uses the mixin.
custom_field_data_models: set[type[CustomFieldDataMixin]] = set()


@event.listens_for(Mapper, "mapper_configured")
def _track_custom_field_data_model(_mapper: Mapper[Any], class_: type) -> None:
    """Register models with custom-field data for admin introspection."""
    if issubclass(class_, CustomFieldDataMixin):
        custom_field_data_models.add(class_)
