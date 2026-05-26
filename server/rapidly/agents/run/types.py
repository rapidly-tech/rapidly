"""Pydantic schemas for run routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from rapidly.models.agent_run import RunStatus, TriggeredByKind


class RunTriggerRequest(BaseModel):
    """Manual run-trigger payload.

    The ``workflow_id`` is in the route URL; this body just carries
    the input. Server-side the action resolves
    ``Workflow.current_version_id`` to pin the run to a specific
    snapshot (or 412 if no version is published yet).
    """

    input_data: dict[str, Any] = Field(default_factory=dict)


class RunSchema(BaseModel):
    id: UUID
    workflow_version_id: UUID
    triggered_by_kind: TriggeredByKind
    triggered_by_id: UUID | None
    status: RunStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
