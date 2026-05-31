"""Pydantic schemas for module endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.project_module import ModuleStatus

ProjectModuleID = Annotated[UUID4, Path(description="The module ID.")]


class ProjectModule(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    lead_id: UUID4 | None = None
    name: str
    description: str | None = None
    status: ModuleStatus
    start_date: datetime | None = None
    target_date: datetime | None = None
    archived_at: datetime | None = None


class ProjectModuleCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = Field(None, max_length=4096)
    lead_id: UUID4 | None = None
    status: ModuleStatus = ModuleStatus.planned
    start_date: datetime | None = None
    target_date: datetime | None = None


class ProjectModuleUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4096)
    lead_id: UUID4 | None = None
    status: ModuleStatus | None = None
    start_date: datetime | None = None
    target_date: datetime | None = None


class ProjectModuleWorkItemAdd(Schema):
    work_item_ids: list[UUID4] = Field(..., min_length=1)
