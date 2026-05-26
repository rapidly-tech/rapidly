"""An execution record of a WorkflowVersion.

A Run is immutable from the API's perspective: callers can list,
get, and cancel-in-flight, but cannot edit fields. The execution
engine (M4.2) is the only writer; it transitions the status
through a state machine (pending → running → terminal) and
populates input_data / output_data / error_message as it walks.

Status semantics:
    pending          — created, waiting for the actor to pick it up
    running          — actor has started the DAG walk
    awaiting_human   — a human-in-the-loop node is parked; resume on
                       a respond-to-prompt call
    succeeded        — walk completed; output_data populated
    failed           — walk hit an error; error_message populated
    cancelled        — the cancel endpoint flipped this; actor exits

Terminal states (succeeded / failed / cancelled) are immutable once
set; the engine's state machine enforces it.

``triggered_by`` is a discriminated reference: the kind tells the
caller how to interpret triggered_by_id (User uuid for a manual
trigger, WebhookTrigger row for a webhook, etc.).
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .workflow_version import WorkflowVersion


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    awaiting_human = "awaiting_human"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


# Terminal states helper — exposed at module scope so the engine
# (M4.2) and tests can both reference the same set.
TERMINAL_RUN_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.succeeded, RunStatus.failed, RunStatus.cancelled}
)


class TriggeredByKind(StrEnum):
    user = "user"
    webhook = "webhook"
    schedule = "schedule"
    sub_workflow = "sub_workflow"


class Run(BaseEntity):
    """An immutable execution record of a WorkflowVersion."""

    __tablename__ = "agent_runs"

    workflow_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workflow_versions.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )

    # Discriminated reference: kind tells the caller how to
    # interpret triggered_by_id (User uuid for manual triggers,
    # WebhookTrigger row for webhooks, etc.). The id is nullable
    # because some trigger kinds (e.g. system-internal) don't have
    # a meaningful target row.
    triggered_by_kind: Mapped[TriggeredByKind] = mapped_column(
        StringEnum(TriggeredByKind, length=16),
        nullable=False,
    )
    triggered_by_id: Mapped[UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )

    status: Mapped[RunStatus] = mapped_column(
        StringEnum(RunStatus, length=16),
        nullable=False,
        default=RunStatus.pending,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    output_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    @declared_attr
    def workflow_version(cls) -> Mapped["WorkflowVersion"]:
        return relationship("WorkflowVersion", lazy="raise")
