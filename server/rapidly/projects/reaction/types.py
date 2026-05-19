"""Pydantic schemas for emoji-reaction endpoints (work items + comments)."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

WorkItemReactionID = Annotated[UUID4, Path(description="The work-item reaction ID.")]
WorkItemCommentReactionID = Annotated[
    UUID4, Path(description="The comment reaction ID.")
]

# Why 32 chars max: leaves room for ZWJ-joined emoji sequences (e.g. the
# rainbow-flag, family, or skin-toned emojis can span ~20 codepoints)
# while blocking arbitrary text dressed up as a reaction.
_REACTION_FIELD = Field(
    ...,
    min_length=1,
    max_length=32,
    description=(
        "Literal emoji string (UTF-8). The frontend picks any emoji; "
        "the backend does not maintain an allowlist."
    ),
)


# ── Work-item reactions ──────────────────────────────────────────────


class WorkItemReaction(IdentifiableSchema, AuditableSchema):
    work_item_id: UUID4
    user_id: UUID4
    reaction: str


class WorkItemReactionCreate(Schema):
    work_item_id: UUID4 = Field(..., description="The work item to react to.")
    reaction: str = _REACTION_FIELD


# ── Comment reactions ────────────────────────────────────────────────


class WorkItemCommentReaction(IdentifiableSchema, AuditableSchema):
    comment_id: UUID4
    user_id: UUID4
    reaction: str


class WorkItemCommentReactionCreate(Schema):
    comment_id: UUID4 = Field(..., description="The comment to react to.")
    reaction: str = _REACTION_FIELD
