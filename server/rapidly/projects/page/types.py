"""Pydantic schemas for project page endpoints."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field, field_validator

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.project_page import ProjectPageAccess

ProjectPageID = Annotated[UUID4, Path(description="The project page ID.")]


class ProjectPage(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    owner_id: UUID4 | None = None
    parent_id: UUID4 | None = None

    name: str
    slug: str
    description_json: dict[str, Any] | None = None
    description_html: str | None = None

    access: ProjectPageAccess
    is_locked: bool
    archived_at: datetime | None = None


class ProjectPageCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    parent_id: UUID4 | None = Field(None, description="Optional parent page.")
    name: Annotated[str, Field(min_length=1, max_length=255)]
    slug: Annotated[str, Field(min_length=1, max_length=255)]
    description_json: dict[str, Any] | None = None
    description_html: str | None = Field(None, max_length=4_194_304)
    access: ProjectPageAccess = ProjectPageAccess.public

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError("slug may only contain a-z, 0-9, and '-'")
        return v


class ProjectPageUpdate(Schema):
    parent_id: UUID4 | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=1, max_length=255)
    description_json: dict[str, Any] | None = None
    description_html: str | None = Field(None, max_length=4_194_304)
    access: ProjectPageAccess | None = None
    is_locked: bool | None = None
