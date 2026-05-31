"""Pydantic schemas for project label CRUD endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.projects.common import HexColor, OptionalHexColor

ProjectLabelID = Annotated[UUID4, Path(description="The project label ID.")]


class ProjectLabel(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    parent_id: UUID4 | None = None
    name: str
    color: str
    description: str | None = None


class ProjectLabelCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    parent_id: UUID4 | None = Field(None, description="Optional parent label.")
    name: Annotated[str, Field(min_length=1, max_length=128)]
    color: HexColor = "#6b7280"
    description: str | None = Field(None, max_length=512)


class ProjectLabelUpdate(Schema):
    parent_id: UUID4 | None = None
    name: str | None = Field(None, min_length=1, max_length=128)
    color: OptionalHexColor = None
    description: str | None = Field(None, max_length=512)
