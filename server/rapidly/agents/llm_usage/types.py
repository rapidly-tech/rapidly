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


class CredentialBudgetRow(BaseModel):
    """One credential's month-to-date utilisation against its cap.

    ``percent_used`` is ``None`` when no budget is set (the cap
    is unlimited, so the question doesn't apply); ``> 1.0`` when
    the credential has blown its monthly budget.
    """

    credential_id: UUID
    workspace_id: UUID
    provider: str
    name: str
    monthly_budget_tokens: int | None
    month_to_date_tokens: int
    percent_used: float | None


class CredentialBudgetResponse(BaseModel):
    """A snapshot of every credential's MTD utilisation.

    ``month_start`` reports the UTC first-of-month anchor used to
    compute MTD so a dashboard doesn't have to derive it.
    """

    month_start: datetime
    rows: list[CredentialBudgetRow]


class CredentialAlertRow(BaseModel):
    """One credential currently in alert state.

    ``triggered_at`` is when the threshold was first crossed
    this month. ``percent_used`` is the MTD percent at the time
    of reading (may be higher than ``threshold_percent`` if
    usage continued after the alert armed).
    """

    credential_id: UUID
    workspace_id: UUID
    provider: str
    name: str
    monthly_budget_tokens: int
    threshold_percent: int
    month_to_date_tokens: int
    percent_used: float
    triggered_at: datetime


class CredentialAlertResponse(BaseModel):
    """Active budget alerts for every credential the caller can see."""

    rows: list[CredentialAlertRow]
