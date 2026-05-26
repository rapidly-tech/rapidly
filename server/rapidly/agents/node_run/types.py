"""Pydantic schemas for node_run routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from rapidly.models.agent_node_run import NodeRunStatus


class NodeRunSchema(BaseModel):
    id: UUID
    run_id: UUID
    node_id: str
    node_type: str
    status: NodeRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    parent_node_run_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
