"""Pydantic schemas for project state CRUD endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.project_state import StateGroup
from rapidly.projects.common import HexColor, OptionalHexColor

ProjectStateID = Annotated[UUID4, Path(description="The project state ID.")]


class ProjectState(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    name: str
    description: str | None = None
    color: str
    group: StateGroup
    sequence: float
    is_default: bool


class ProjectStateCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    name: Annotated[str, Field(min_length=1, max_length=128)]
    description: str | None = Field(None, max_length=512)
    color: HexColor = "#6b7280"
    group: StateGroup
    sequence: float = 1000.0
    is_default: bool = False


class ProjectStateUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    color: OptionalHexColor = None
    group: StateGroup | None = None
    sequence: float | None = None
    is_default: bool | None = None
