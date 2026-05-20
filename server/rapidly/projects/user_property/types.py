"""Pydantic schemas for project-user-property endpoints."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

ProjectUserPropertyID = Annotated[
    UUID4, Path(description="The project-user-property ID.")
]


class ProjectUserProperty(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    user_id: UUID4
    filters: dict[str, Any]
    display_filters: dict[str, Any]
    display_properties: dict[str, Any]


class ProjectUserPropertyUpsert(Schema):
    """Upsert payload — all fields optional, anything omitted keeps its
    current value (or its default-empty dict if the row is new).
    """

    project_id: UUID4 = Field(
        ..., description="The project these preferences belong to."
    )
    filters: dict[str, Any] | None = None
    display_filters: dict[str, Any] | None = None
    display_properties: dict[str, Any] | None = None
