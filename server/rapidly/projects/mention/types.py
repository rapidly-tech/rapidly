"""Pydantic schemas for work-item-mention endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

WorkItemMentionID = Annotated[UUID4, Path(description="The work-item-mention ID.")]


class WorkItemMention(IdentifiableSchema, AuditableSchema):
    comment_id: UUID4
    mentioned_user_id: UUID4
    mentioned_by_id: UUID4 | None


class WorkItemMentionCreate(Schema):
    comment_id: UUID4 = Field(
        ..., description="The comment in which the mention appears."
    )
    mentioned_user_id: UUID4 = Field(
        ...,
        description=(
            "The user being mentioned. Must be a member of the comment's "
            "workspace (the comment's work-item's project's workspace)."
        ),
    )
