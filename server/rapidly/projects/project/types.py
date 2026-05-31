"""Pydantic schemas for project CRUD endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field, field_validator

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.project import ProjectVisibility
from rapidly.projects.common import OptionalHexColor

ProjectID = Annotated[UUID4, Path(description="The project ID.")]


# ── Read models ──


class Project(IdentifiableSchema, AuditableSchema):
    workspace_id: UUID4 = Field(..., description="Owning workspace.")
    owner_id: UUID4 = Field(..., description="User who owns the project.")

    name: str = Field(..., description="Display name.")
    identifier: str = Field(..., description="Short prefix used in work-item IDs.")
    slug: str = Field(..., description="URL-safe slug, unique per workspace.")
    description: str | None = Field(None, description="Free-form description.")

    visibility: ProjectVisibility = Field(..., description="private | public.")

    emoji: str | None = Field(None, description="Optional emoji icon.")
    color: OptionalHexColor = None
    cover_image_url: str | None = Field(None, description="Optional cover image URL.")

    is_cycles_enabled: bool
    is_modules_enabled: bool
    is_views_enabled: bool
    is_pages_enabled: bool
    is_intake_enabled: bool

    archived_at: datetime | None = Field(
        None, description="Set when the project is archived."
    )


# ── Mutation payloads ──


class ProjectCreate(Schema):
    workspace_id: UUID4 = Field(..., description="Owning workspace.")
    name: Annotated[
        str, Field(min_length=1, max_length=255, description="Display name.")
    ]
    identifier: Annotated[
        str,
        Field(
            min_length=2, max_length=12, description="Short prefix for work-item IDs."
        ),
    ]
    slug: Annotated[
        str, Field(min_length=2, max_length=64, description="URL-safe slug.")
    ]
    description: str | None = Field(None, max_length=4096)
    visibility: ProjectVisibility = ProjectVisibility.private
    emoji: str | None = Field(None, max_length=16)
    color: OptionalHexColor = None
    cover_image_url: str | None = Field(None, max_length=2048)

    is_cycles_enabled: bool = True
    is_modules_enabled: bool = True
    is_views_enabled: bool = True
    is_pages_enabled: bool = True
    is_intake_enabled: bool = False

    @field_validator("identifier")
    @classmethod
    def _upper_identifier(cls, v: str) -> str:
        v = v.strip().upper()
        if not v.isalnum():
            raise ValueError("identifier must be alphanumeric")
        return v

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError("slug may only contain a-z, 0-9, and '-'")
        return v


class ProjectUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4096)
    visibility: ProjectVisibility | None = None
    emoji: str | None = Field(None, max_length=16)
    color: OptionalHexColor = None
    cover_image_url: str | None = Field(None, max_length=2048)

    is_cycles_enabled: bool | None = None
    is_modules_enabled: bool | None = None
    is_views_enabled: bool | None = None
    is_pages_enabled: bool | None = None
    is_intake_enabled: bool | None = None
