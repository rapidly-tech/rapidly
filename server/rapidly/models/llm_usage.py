"""Per-call LLM usage record.

Written by the LLM + structured-output handlers after each
successful provider call. One row per node-run that talks to an
LLM provider; structured queries roll up by workspace + provider
+ credential + time window for billing dashboards and per-key
budget alerts (M4.7e).

Why a separate table, not just NodeRun.output_data:
    NodeRun.output_data is opaque JSON — we'd need a per-row scan
    + JSON extraction to aggregate usage. A typed table makes
    "tokens spent by ws_X last 24h" a single indexed query.

Why ``credential_id`` is nullable:
    Calls that fall through to the env-var path don't have a
    credential row to point at. Filtering rollups by
    ``credential_id IS NOT NULL`` gives the per-credential split;
    summing across both gives the workspace total.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .integration_credential import IntegrationCredential
    from .workspace import Workspace


class LlmUsage(BaseEntity):
    """One LLM provider call's token counts + tenancy context."""

    __tablename__ = "llm_usage"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    # Nullable for env-fallback calls. Set-null on credential
    # delete so historical usage rows survive credential
    # rotation — operators care about "how much did we spend
    # under this provider" even after the key is gone.
    credential_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("integration_credentials.id", ondelete="set null"),
        nullable=True,
        index=True,
    )
    # Workflow run context — nullable for handlers invoked
    # outside an engine context (none today, but future eval/
    # smoke-test callers don't have a run).
    run_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("agent_runs.id", ondelete="set null"),
        nullable=True,
        index=True,
    )
    node_run_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("agent_node_runs.id", ondelete="set null"),
        nullable=True,
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Model identifier as the handler was configured (e.g.,
    # ``text-embedding-3-small``, ``gpt-4o-mini``). Not the
    # full ``provider:model`` shape — we already have provider
    # in its own column for index-friendly filters.
    model: Mapped[str] = mapped_column(String(128), nullable=False)

    # BigInteger so a single 1M-token batch doesn't wrap an
    # int32 column at ~2B (the workspace-lifetime sum would
    # blow the limit fast on a busy account).
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Server-side default on insert so the row carries the actual
    # database time regardless of the application clock. The
    # ``BaseEntity`` mixin's ``created_at`` already does this,
    # but rollup queries hit ``occurred_at`` so we keep a
    # dedicated index here for time-window filters.
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    @declared_attr
    def credential(cls) -> Mapped["IntegrationCredential | None"]:
        return relationship("IntegrationCredential", lazy="raise")

    @property
    def total_tokens(self) -> int:
        """Sum of input + output. Computed property so we don't
        have to dual-write at insert time + risk drift if the
        provider changes their accounting later.
        """
        return self.input_tokens + self.output_tokens
