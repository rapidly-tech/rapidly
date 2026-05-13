"""Pydantic schemas for work-item CRUD endpoints."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.work_item import WorkItemPriority

WorkItemID = Annotated[UUID4, Path(description="The work-item ID.")]


# ── Read model ──


class WorkItem(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    sequence_number: int
    name: str
    description_json: dict[str, Any] | None = None
    description_html: str | None = None

    priority: WorkItemPriority
    state_id: UUID4
    estimate_point_id: UUID4 | None = None
    parent_id: UUID4 | None = None

    start_date: datetime | None = None
    target_date: datetime | None = None
    completed_at: datetime | None = None

    sort_order: float
    is_draft: bool
    archived_at: datetime | None = None

    assignee_ids: list[UUID4] = Field(
        default_factory=list, description="Users currently assigned."
    )
    label_ids: list[UUID4] = Field(
        default_factory=list, description="Labels currently applied."
    )


# ── Mutation payloads ──


class WorkItemCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    name: Annotated[str, Field(min_length=1, max_length=512)]
    description_json: dict[str, Any] | None = None
    description_html: str | None = Field(None, max_length=1_048_576)

    priority: WorkItemPriority = WorkItemPriority.none
    state_id: UUID4 = Field(..., description="Workflow state for this work item.")
    estimate_point_id: UUID4 | None = None
    parent_id: UUID4 | None = Field(
        None, description="Parent work item if this is a sub-item."
    )

    start_date: datetime | None = None
    target_date: datetime | None = None

    sort_order: float | None = Field(
        None, description="Display order; defaults to end-of-list if omitted."
    )
    is_draft: bool = False

    assignee_ids: list[UUID4] = Field(default_factory=list)
    label_ids: list[UUID4] = Field(default_factory=list)


class WorkItemUpdate(Schema):
    name: str | None = Field(None, min_length=1, max_length=512)
    description_json: dict[str, Any] | None = None
    description_html: str | None = Field(None, max_length=1_048_576)

    priority: WorkItemPriority | None = None
    state_id: UUID4 | None = None
    estimate_point_id: UUID4 | None = None
    parent_id: UUID4 | None = None

    start_date: datetime | None = None
    target_date: datetime | None = None
    completed_at: datetime | None = None

    sort_order: float | None = None
    is_draft: bool | None = None

    assignee_ids: list[UUID4] | None = Field(
        None, description="Full replacement of the assignee set when present."
    )
    label_ids: list[UUID4] | None = Field(
        None, description="Full replacement of the label set when present."
    )
