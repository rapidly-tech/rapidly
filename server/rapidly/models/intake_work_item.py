"""Triage state for an incoming work item.

An ``IntakeWorkItem`` is a thin wrapper around an existing ``WorkItem``
that captures *how* the item arrived (form submission, email, API)
and *what triage decision* has been made.  Mirrors Plane's
``IntakeIssue``.

Why a one-to-one join with WorkItem (rather than columns on WorkItem
itself):

- Not every work item enters via intake. Putting the columns on the
  base model would force every row to carry NULL triage state.
- Decoupling lets the intake submodule evolve (snooze timers,
  duplicate-of pointers, custom intake views) without churning the
  work-item table.

The WorkItem itself stays the source of truth for content; the
intake row only tracks triage state.
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .work_item import WorkItem


class IntakeStatus(StrEnum):
    """Triage outcome state machine.

    ``pending`` → one of ``{accepted, declined, snoozed, duplicate}``.
    Snoozed rows return to ``pending`` automatically when
    ``snoozed_until`` passes (worker out of scope here; the API just
    treats a past snooze as "pending again" for filtering).
    """

    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    snoozed = "snoozed"
    duplicate = "duplicate"


class IntakeSource(StrEnum):
    """How the work item arrived. ``api`` is the catch-all."""

    api = "api"
    email = "email"
    form = "form"
    integration = "integration"


class IntakeWorkItem(BaseEntity):
    """Triage state for one work item in a project's intake queue."""

    __tablename__ = "intake_work_items"
    __table_args__ = (
        UniqueConstraint("work_item_id", name="intake_work_items_work_item_id_key"),
    )

    work_item_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    status: Mapped[IntakeStatus] = mapped_column(
        StringEnum(IntakeStatus, length=16),
        nullable=False,
        default=IntakeStatus.pending,
        index=True,
    )
    source: Mapped[IntakeSource] = mapped_column(
        StringEnum(IntakeSource, length=16),
        nullable=False,
        default=IntakeSource.api,
    )

    # The address the request came from when source=email — informational
    # only; we don't try to keep the thread alive.
    source_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    snoozed_until: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Set when status=duplicate. FK to WorkItem so the cascade catches
    # the case where the canonical item is deleted (the intake row
    # then loses its pointer and would need re-triage).
    duplicate_to_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    triaged_by_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )
    triaged_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship(
            "WorkItem",
            lazy="raise",
            foreign_keys="IntakeWorkItem.work_item_id",
        )

    @declared_attr
    def duplicate_to(cls) -> Mapped["WorkItem | None"]:
        return relationship(
            "WorkItem",
            lazy="raise",
            foreign_keys="IntakeWorkItem.duplicate_to_id",
        )
