"""Event-type CRUD payloads and response models.

Defines the ``EventTypeUpdate`` mutation input, the ``EventType`` read model
with workspace ownership, and ``EventTypeWithStats`` which extends it with
time-range and occurrence statistics for list endpoints.
"""

from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field, field_validator

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.event import EventSource

# ---------------------------------------------------------------------------
# Path parameter helper
# ---------------------------------------------------------------------------

EventTypeID = Annotated[UUID4, Path(description="The event type ID.")]


# ---------------------------------------------------------------------------
# Mutation payloads
# ---------------------------------------------------------------------------


class EventTypeUpdate(Schema):
    label: str | None = Field(
        None, description="The label for the event type.", min_length=1, max_length=128
    )
    label_property_selector: str | None = Field(
        None,
        description=(
            "Property path to extract dynamic label from event metadata "
            "(e.g., 'subject' or 'metadata.subject')."
        ),
        min_length=1,
        max_length=256,
    )

    @field_validator("label")
    @classmethod
    def strip_and_validate_label(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Label cannot be empty or only whitespace")
        return cleaned

    @field_validator("label_property_selector")
    @classmethod
    def strip_and_validate_label_property_selector(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return v


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


class EventType(IdentifiableSchema, AuditableSchema):
    name: str = Field(..., description="The name of the event type.")
    label: str = Field(..., description="The label for the event type.")
    label_property_selector: str | None = Field(
        None,
        description="Property path to extract dynamic label from event metadata.",
    )
    workspace_id: UUID4 = Field(
        ..., description="The ID of the workspace owning the event type."
    )


class EventTypeWithStats(EventType):
    """Event type with aggregated occurrence statistics."""

    source: EventSource = Field(
        description="The source of the events (system or user)."
    )
    occurrences: int = Field(description="Number of times the event has occurred.")
    first_seen: datetime = Field(description="The first time the event occurred.")
    last_seen: datetime = Field(description="The last time the event occurred.")
