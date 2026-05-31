"""Pydantic schemas for cycle endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

ProjectCycleID = Annotated[UUID4, Path(description="The cycle ID.")]


class ProjectCycle(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    owner_id: UUID4 | None = None
    name: str
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    archived_at: datetime | None = None


class ProjectCycleCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = Field(None, max_length=4096)
    start_date: datetime | None = None
    end_date: datetime | None = None


class ProjectCycleUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4096)
    start_date: datetime | None = None
    end_date: datetime | None = None


class ProjectCycleWorkItemAdd(Schema):
    work_item_ids: list[UUID4] = Field(..., min_length=1)
