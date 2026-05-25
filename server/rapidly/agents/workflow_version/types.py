"""Pydantic schemas for workflow_version routes.

The graph_json shape (nodes + edges) lives in the editor's TS
module + a Zod schema on the frontend. The backend stores it as
opaque JSONB so a graph-schema evolution doesn't require a column
migration. We validate that it's an object with the expected top-
level keys; the per-node shape is the editor's contract."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class WorkflowVersionCreate(BaseModel):
    """Publish a new version of a workflow's graph.

    The route URL carries the workflow_id; the body just carries the
    graph_json. ``version_number`` is server-assigned (next
    monotonically increasing per workflow).
    """

    graph_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("graph_json")
    @classmethod
    def _validate_graph_shape(cls, v: dict[str, Any]) -> dict[str, Any]:
        # Light shape check: the editor sends {nodes: [...], edges:
        # [...]}. Reject obviously malformed payloads so a stored
        # snapshot is at minimum addressable by the runtime walker.
        # The DB itself is JSONB and would accept anything; this
        # boundary keeps the contract honest.
        if "nodes" not in v or "edges" not in v:
            raise ValueError("graph_json must include nodes and edges keys")
        if not isinstance(v.get("nodes"), list) or not isinstance(v.get("edges"), list):
            raise ValueError("graph_json.nodes and .edges must be lists")
        return v


class WorkflowVersionSchema(BaseModel):
    id: UUID
    workflow_id: UUID
    version_number: int
    graph_json: dict[str, Any]
    created_by_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
