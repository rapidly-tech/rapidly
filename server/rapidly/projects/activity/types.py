"""Pydantic schemas for work-item activity endpoints."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4

from rapidly.core.types import AuditableSchema, IdentifiableSchema
from rapidly.models.work_item_activity import WorkItemActivityVerb

WorkItemActivityID = Annotated[UUID4, Path(description="The activity ID.")]


class WorkItemActivity(IdentifiableSchema, AuditableSchema):
    work_item_id: UUID4
    actor_id: UUID4 | None = None
    verb: WorkItemActivityVerb
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    payload: dict[str, Any] | None = None
    comment_id: UUID4 | None = None
