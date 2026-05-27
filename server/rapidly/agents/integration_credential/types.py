"""Pydantic schemas for the IntegrationCredential API surface.

Response schemas deliberately omit the secret value — the secret
is write-only via the API. Operators rotate by deleting +
creating (or by issuing a new credential and updating workflows
to reference it).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# Free-form provider identifier — must match what the embedder /
# llm_handler dispatch expects (currently: openai, anthropic,
# google, ollama). Pattern keeps it identifier-safe.
_PROVIDER_PATTERN = r"^[a-z0-9_-]+$"


class IntegrationCredentialCreate(BaseModel):
    """Create payload. ``secret`` is the plaintext — encrypted at
    rest by the action layer.
    """

    workspace_id: UUID
    provider: str = Field(
        min_length=1,
        max_length=64,
        pattern=_PROVIDER_PATTERN,
        description=(
            "Provider identifier matching the embedder/llm dispatch — "
            "examples: ``openai``, ``anthropic``, ``google``, ``ollama``."
        ),
    )
    name: str = Field(
        min_length=1,
        max_length=128,
        description=(
            "Operator-facing label, e.g., ``production`` or ``eu-region``. "
            "Multiple credentials per (workspace, provider) are allowed."
        ),
    )
    secret: str = Field(
        min_length=1,
        max_length=4096,
        description="API key plaintext. Encrypted at rest with the app Fernet key.",
    )
    base_url: str | None = Field(
        default=None,
        max_length=512,
        description=(
            "Override for self-hosted endpoints (Ollama, LocalAI). "
            "Null falls back to the provider's canonical hostname."
        ),
    )
    is_default: bool = Field(
        default=False,
        description=(
            "When true, this credential resolves on lookup by (workspace, "
            "provider) without naming a specific id. Only one default per "
            "pair is allowed (enforced by partial unique index)."
        ),
    )
    monthly_budget_tokens: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Monthly token cap (input + output, summed). Null = unlimited. "
            "Used by the /budgets endpoint to report utilisation."
        ),
    )
    budget_alert_threshold_percent: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description=(
            "Alert threshold as a whole-percent integer (1-100). When "
            "MTD usage crosses this percent of ``monthly_budget_tokens`` "
            "the credential lands in the alerts endpoint. Null = no "
            "alerting. Useless without ``monthly_budget_tokens`` set."
        ),
    )


class IntegrationCredentialSchema(BaseModel):
    """Response shape. **Never** includes the secret plaintext."""

    id: UUID
    workspace_id: UUID
    provider: str
    name: str
    base_url: str | None
    is_default: bool
    monthly_budget_tokens: int | None
    budget_alert_threshold_percent: int | None
    budget_alert_triggered_at: datetime | None
    created_at: datetime
    modified_at: datetime | None

    model_config = {"from_attributes": True}
