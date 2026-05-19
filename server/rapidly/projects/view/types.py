"""Pydantic schemas for project saved-view endpoints."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.project_view import ProjectViewAccess

ProjectViewID = Annotated[UUID4, Path(description="The project-view ID.")]


class ProjectView(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    owner_id: UUID4 | None
    name: str
    description: str | None
    filters: dict[str, Any]
    display_filters: dict[str, Any]
    display_properties: dict[str, Any]
    access: ProjectViewAccess
    is_locked: bool
    sort_order: float


class ProjectViewCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4_194_304)
    filters: dict[str, Any] = Field(default_factory=dict)
    display_filters: dict[str, Any] = Field(default_factory=dict)
    display_properties: dict[str, Any] = Field(default_factory=dict)
    access: ProjectViewAccess = ProjectViewAccess.public


class ProjectViewUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4_194_304)
    filters: dict[str, Any] | None = None
    display_filters: dict[str, Any] | None = None
    display_properties: dict[str, Any] | None = None
    access: ProjectViewAccess | None = None
    is_locked: bool | None = None
    sort_order: float | None = None
