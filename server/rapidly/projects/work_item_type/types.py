"""Pydantic schemas for work-item-type endpoints."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

WorkItemTypeID = Annotated[UUID4, Path(description="The work-item type ID.")]


class WorkItemType(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    name: str
    description: str | None
    logo_props: dict[str, Any]
    is_epic: bool
    is_default: bool
    is_active: bool
    sort_order: float


class WorkItemTypeCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4_194_304)
    logo_props: dict[str, Any] = Field(default_factory=dict)
    is_epic: bool = False
    is_default: bool = False
    is_active: bool = True
    sort_order: float | None = None


class WorkItemTypeUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4_194_304)
    logo_props: dict[str, Any] | None = None
    is_epic: bool | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    sort_order: float | None = None
