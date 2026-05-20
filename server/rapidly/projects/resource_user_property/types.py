"""Pydantic schemas for cycle/module user-property endpoints."""

from typing import Any

from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

# ── Cycles ───────────────────────────────────────────────────────────


class ProjectCycleUserProperty(IdentifiableSchema, AuditableSchema):
    cycle_id: UUID4
    user_id: UUID4
    filters: dict[str, Any]
    display_filters: dict[str, Any]
    display_properties: dict[str, Any]


class ProjectCycleUserPropertyUpsert(Schema):
    cycle_id: UUID4 = Field(..., description="The cycle these preferences belong to.")
    filters: dict[str, Any] | None = None
    display_filters: dict[str, Any] | None = None
    display_properties: dict[str, Any] | None = None


# ── Modules ──────────────────────────────────────────────────────────


class ProjectModuleUserProperty(IdentifiableSchema, AuditableSchema):
    module_id: UUID4
    user_id: UUID4
    filters: dict[str, Any]
    display_filters: dict[str, Any]
    display_properties: dict[str, Any]


class ProjectModuleUserPropertyUpsert(Schema):
    module_id: UUID4 = Field(..., description="The module these preferences belong to.")
    filters: dict[str, Any] | None = None
    display_filters: dict[str, Any] | None = None
    display_properties: dict[str, Any] | None = None
