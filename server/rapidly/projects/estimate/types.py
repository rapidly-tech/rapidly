"""Pydantic schemas for project estimate (and estimate-point) endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.project_estimate import EstimateType

ProjectEstimateID = Annotated[UUID4, Path(description="The project estimate ID.")]
ProjectEstimatePointID = Annotated[UUID4, Path(description="The estimate point ID.")]


# ── Estimate ──


class ProjectEstimate(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    name: str
    description: str | None = None
    type: EstimateType
    is_active: bool


class ProjectEstimateCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    name: Annotated[str, Field(min_length=1, max_length=128)]
    description: str | None = Field(None, max_length=512)
    type: EstimateType = EstimateType.points
    is_active: bool = False


class ProjectEstimateUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    type: EstimateType | None = None
    is_active: bool | None = None


# ── Estimate points ──


class ProjectEstimatePoint(IdentifiableSchema, AuditableSchema):
    estimate_id: UUID4
    key: int
    value: str
    description: str | None = None


class ProjectEstimatePointCreate(Schema):
    estimate_id: UUID4 = Field(..., description="Owning estimate scale.")
    key: Annotated[int, Field(ge=0, le=10000)]
    value: Annotated[str, Field(min_length=1, max_length=64)]
    description: str | None = Field(None, max_length=512)


class ProjectEstimatePointUpdate(Schema):
    key: int | None = Field(None, ge=0, le=10000)
    value: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = Field(None, max_length=512)
