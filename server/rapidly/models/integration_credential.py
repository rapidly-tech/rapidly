"""Per-workspace credentials for outbound integrations.

Stores API keys (and optional base URLs) for the LLM + embedding
providers the Agents chamber dispatches to. A workspace can have
multiple credentials per provider — e.g., one named ``production``
and one named ``staging`` pointing at different Ollama hosts —
but only one is marked ``is_default`` per (workspace, provider)
pair via a partial unique index.

Why per-workspace, not global:
    A multi-tenant deployment needs per-tenant billing isolation
    on the LLM-provider side. A single shared env-var key would
    bill every workspace's usage to one account. The handler
    resolves the credential at runtime via the Run's workspace
    so a workflow's LLM costs stay inside the tenant boundary.

Secret value is encrypted at rest with the app's Fernet key
(``settings.SECRET``). The decrypt path lives in the queries
module so consumers can't accidentally serialise the plaintext
into a response model.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .workspace import Workspace


class IntegrationCredential(BaseEntity):
    """A workspace's API key for one outbound integration."""

    __tablename__ = "integration_credentials"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    # Free-form provider identifier matching the embedder /
    # llm_handler dispatch ("openai", "anthropic", "google",
    # "ollama"). Free-form rather than enum so a new provider
    # can land in the handler without a migration here.
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Human label — operators may want multiple credentials per
    # provider (production, staging, eu-region). Surfaced in
    # the UI for selection; not used in dispatch.
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Fernet-encrypted secret. Plaintext never lives in the model.
    # The decrypt path is in queries.py so accidental
    # ``.model_dump()`` calls can't leak it.
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional override for self-hosted endpoints (Ollama,
    # LocalAI, vLLM). When null the dispatch uses the provider's
    # canonical hostname.
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Marks the default credential for ``provider`` in this
    # workspace. The handler picks the default when the workflow
    # doesn't name a specific credential. Enforced by partial
    # unique index in the migration (only one ``is_default=true``
    # per workspace+provider).
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Monthly budget cap in tokens (input + output, summed). Nullable
    # = unlimited. Operators set it to bound a tenant's spend on a
    # provider; the budgets endpoint reports current month-to-date
    # consumption against this cap so dashboards can render
    # utilisation. We store tokens not dollars because provider
    # price tables drift — the UI converts to dollars at display
    # time against whatever rate card the operator configures.
    monthly_budget_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Alert threshold as a whole-percent integer (e.g., 80 = 80% of
    # monthly_budget_tokens). Null = no alerting. The LLM handler
    # checks this after each LlmUsage write — when MTD consumption
    # crosses the threshold for the first time this month,
    # ``budget_alert_triggered_at`` is set to ``now_utc()`` so the
    # alerts endpoint surfaces it. Operators subscribe via webhook
    # or poll the endpoint; we deliberately don't push notifications
    # here because notification dispatch is its own concern (Slack,
    # email, on-call) that operators wire up however they want.
    budget_alert_threshold_percent: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # Set the first time MTD crosses the threshold each month. The
    # alerts endpoint compares this timestamp's calendar month to
    # the current month — if they match, the alert is "active". On
    # a new month MTD resets and this naturally becomes stale,
    # so a re-cross gets a fresh alert.
    budget_alert_triggered_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")
