"""Append-only audit trail for a work item.

Every mutation that meaningfully changes a work item — state change,
priority bump, comment added, assignee toggled — leaves one row here.
The table is write-only at the action layer; deletes happen only via
the normal soft-delete + retention sweep paths.

Free-form fields (``field``, ``old_value``, ``new_value``,
``payload``) are intentionally untyped so the emit call sites can
describe whichever change they like without an ALTER TABLE.  The UI
renders activity through a verb-keyed switch — adding a new verb is
non-breaking.
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .user import User
    from .work_item import WorkItem
    from .work_item_comment import WorkItemComment


class WorkItemActivityVerb(StrEnum):
    """The change-of-shape that produced this activity row.

    Stored as a string so adding a verb doesn't require a migration.
    Renderers fall back gracefully on unknown verbs.
    """

    created = "created"
    updated = "updated"
    state_changed = "state_changed"
    priority_changed = "priority_changed"
    assignee_added = "assignee_added"
    assignee_removed = "assignee_removed"
    label_added = "label_added"
    label_removed = "label_removed"
    comment_added = "comment_added"
    archived = "archived"
    unarchived = "unarchived"


class WorkItemActivity(BaseEntity):
    """One audit-log entry."""

    __tablename__ = "work_item_activities"

    work_item_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    # Nullable for system-emitted events (cron jobs, integrations).
    actor_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    verb: Mapped[WorkItemActivityVerb] = mapped_column(
        StringEnum(WorkItemActivityVerb, length=32),
        nullable=False,
        index=True,
    )

    # Optional structured fields for diff-style verbs.  ``payload``
    # carries anything that doesn't fit the field/old/new triplet.
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    old_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    comment_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("work_item_comments.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")

    @declared_attr
    def actor(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")

    @declared_attr
    def comment(cls) -> Mapped["WorkItemComment | None"]:
        return relationship("WorkItemComment", lazy="raise")
