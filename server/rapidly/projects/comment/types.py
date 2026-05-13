"""Pydantic schemas for work-item comment endpoints."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

WorkItemCommentID = Annotated[UUID4, Path(description="The work-item comment ID.")]


class WorkItemComment(IdentifiableSchema, AuditableSchema):
    work_item_id: UUID4
    actor_id: UUID4
    body_json: dict[str, Any] | None = None
    body_html: str


class WorkItemCommentCreate(Schema):
    work_item_id: UUID4 = Field(..., description="Target work item.")
    body_html: Annotated[str, Field(min_length=1, max_length=1_048_576)]
    body_json: dict[str, Any] | None = None


class WorkItemCommentUpdate(Schema):
    body_html: str | None = Field(None, min_length=1, max_length=1_048_576)
    body_json: dict[str, Any] | None = None
