"""Pydantic schemas for project-view endpoints."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

ProjectViewID = Annotated[UUID4, Path(description="The view ID.")]


class ProjectView(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    owner_id: UUID4 | None = None
    name: str
    description: str | None = None
    # The ``filters`` blob mirrors GET /api/work-items/ query params:
    # keys like state_id, priority, label_id (all lists); parent_id,
    # include_archived, include_drafts as scalars.  No DB-side schema
    # so older API versions stay forward-compatible.
    filters: dict[str, Any] = Field(default_factory=dict)
    archived_at: datetime | None = None


class ProjectViewCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = Field(None, max_length=4096)
    filters: dict[str, Any] = Field(default_factory=dict)


class ProjectViewUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4096)
    filters: dict[str, Any] | None = None
