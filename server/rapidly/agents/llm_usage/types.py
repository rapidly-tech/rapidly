"""Pydantic schemas for the LlmUsage read surface."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LlmUsageSchema(BaseModel):
    id: UUID
    workspace_id: UUID
    credential_id: UUID | None
    run_id: UUID | None
    node_run_id: UUID | None
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    occurred_at: datetime

    model_config = {"from_attributes": True}


class UsageRollupRow(BaseModel):
    """One row of a grouped usage aggregate.

    ``credential_id`` is null for env-fallback / explicit-key
    calls. The rollup groups null and non-null separately so
    dashboards can show "untagged" usage distinctly from per-key
    splits.
    """

    workspace_id: UUID
    credential_id: UUID | None
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    call_count: int


class UsageRollupResponse(BaseModel):
    """A grouped rollup over a time window.

    ``window_start`` + ``window_end`` reflect the actual filter
    applied (default: last 24h), so a client doesn't have to
    re-derive the window from its own request.
    """

    window_start: datetime
    window_end: datetime
    rows: list[UsageRollupRow]
