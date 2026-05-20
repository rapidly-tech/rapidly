"""Pydantic schemas for sticky-note endpoints."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

StickyID = Annotated[UUID4, Path(description="The sticky ID.")]

# Restrict to ``#`` + 6 hex chars so the column can't carry arbitrary
# text dressed up as a colour.  The frontend palette uses only this
# format anyway.
_HEX_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class Sticky(IdentifiableSchema, AuditableSchema):
    workspace_id: UUID4
    owner_id: UUID4
    name: str
    description_json: dict[str, Any] | None = None
    description_html: str | None = None
    color: str | None
    sort_order: float


class StickyCreate(Schema):
    workspace_id: UUID4 = Field(
        ..., description="The workspace this sticky belongs to."
    )
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description_json: dict[str, Any] | None = None
    description_html: str | None = Field(None, max_length=1_048_576)
    color: str | None = Field(None, pattern=_HEX_COLOR_PATTERN)
    sort_order: float | None = None


class StickyUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description_json: dict[str, Any] | None = None
    description_html: str | None = Field(None, max_length=1_048_576)
    color: str | None = Field(None, pattern=_HEX_COLOR_PATTERN)
    sort_order: float | None = None
