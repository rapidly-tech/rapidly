"""Pydantic schemas for work-item external links."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, AnyUrl, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

WorkItemLinkID = Annotated[UUID4, Path(description="The work-item link ID.")]


class WorkItemLink(IdentifiableSchema, AuditableSchema):
    work_item_id: UUID4
    created_by_id: UUID4 | None
    url: str
    title: str | None


class WorkItemLinkCreate(Schema):
    work_item_id: UUID4 = Field(..., description="The work item the link belongs to.")
    url: AnyUrl = Field(
        ...,
        description="Absolute URL — http/https only. Validated by AnyUrl.",
    )
    title: str | None = Field(
        None,
        max_length=255,
        description="Optional display label. Falls back to the URL when empty.",
    )


class WorkItemLinkUpdate(Schema):
    url: AnyUrl | None = None
    title: str | None = Field(None, max_length=255)
