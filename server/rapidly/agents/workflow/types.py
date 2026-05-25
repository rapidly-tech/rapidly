"""Pydantic schemas for the workflow API surface."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    """Create payload. ``current_version_id`` is set later by the
    versioning submodule's "publish" call, not at create-time."""

    workspace_id: UUID
    project_id: UUID | None = None
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None


class WorkflowUpdate(BaseModel):
    """Update payload. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    project_id: UUID | None = None
    current_version_id: UUID | None = None


class WorkflowSchema(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID | None
    name: str
    description: str | None
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
