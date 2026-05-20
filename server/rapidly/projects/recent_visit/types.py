"""Pydantic schemas for recent-visit endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.recent_visit import RecentVisitEntityType

RecentVisitID = Annotated[UUID4, Path(description="The recent-visit row ID.")]


class RecentVisit(IdentifiableSchema, AuditableSchema):
    user_id: UUID4
    workspace_id: UUID4
    entity_type: RecentVisitEntityType
    entity_id: UUID4
    visited_at: datetime


class RecentVisitRecord(Schema):
    """Record a visit. Bumps ``visited_at`` if a row already exists
    for ``(caller, entity_type, entity_id)``; otherwise inserts.
    """

    workspace_id: UUID4 = Field(..., description="The workspace the entity lives in.")
    entity_type: RecentVisitEntityType
    entity_id: UUID4
