"""Pydantic schemas for intake-work-item endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import UUID4, EmailStr, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.intake_work_item import IntakeSource, IntakeStatus

IntakeWorkItemID = Annotated[UUID4, Path(description="The intake-work-item ID.")]


class IntakeWorkItem(IdentifiableSchema, AuditableSchema):
    work_item_id: UUID4
    status: IntakeStatus
    source: IntakeSource
    source_email: str | None
    snoozed_until: datetime | None
    duplicate_to_id: UUID4 | None
    triaged_by_id: UUID4 | None
    triaged_at: datetime | None


class IntakeWorkItemCreate(Schema):
    """Drop a work item into the project intake queue.

    The work item must already exist (typically created via the public
    intake form, an email-ingest worker, or an integration).  The
    intake row is the *triage* state on top of that work item.
    """

    work_item_id: UUID4 = Field(..., description="The work item to triage.")
    source: IntakeSource = IntakeSource.api
    source_email: EmailStr | None = Field(
        None,
        description="Used when source=email — the originating address.",
    )


class IntakeWorkItemUpdate(Schema):
    """Triage transition. Sets ``triaged_by_id``/``triaged_at`` server-side.

    Validation in actions: status=snoozed requires ``snoozed_until`` in
    the future; status=duplicate requires ``duplicate_to_id``.
    """

    status: IntakeStatus
    snoozed_until: datetime | None = None
    duplicate_to_id: UUID4 | None = None
