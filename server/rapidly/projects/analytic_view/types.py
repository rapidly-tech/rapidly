"""Pydantic schemas for analytic-view endpoints."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

AnalyticViewID = Annotated[UUID4, Path(description="The analytic-view ID.")]


class AnalyticView(IdentifiableSchema, AuditableSchema):
    workspace_id: UUID4
    project_id: UUID4 | None
    created_by_id: UUID4 | None
    name: str
    description: str | None
    query: dict[str, Any]


class AnalyticViewCreate(Schema):
    workspace_id: UUID4 = Field(
        ..., description="The workspace this dashboard belongs to."
    )
    project_id: UUID4 | None = Field(
        None,
        description=(
            "Optional project filter. When null, the dashboard spans every "
            "project in the workspace."
        ),
    )
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4_194_304)
    query: dict[str, Any] = Field(default_factory=dict)


class AnalyticViewUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4_194_304)
    query: dict[str, Any] | None = None
