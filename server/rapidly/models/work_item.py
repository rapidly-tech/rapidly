"""Work-item model: the central unit of work inside a project.

Mirrors the shape of Plane's ``Issue`` (renamed internally to
``WorkItem``).  Each row belongs to exactly one project and exactly
one workflow state; assignees and labels are tracked via separate
many-to-many tables.

The ``sequence_number`` column gives each work item a project-scoped
integer (``PRJ-1``, ``PRJ-2``, …) for human-friendly IDs.  Uniqueness
is enforced at the DB layer; the create action computes the next
number under the row-level lock that the unique constraint
implicitly provides.

Description fields are stored in three forms so the same record can
back both plain HTML rendering and a Yjs-backed collaborative editor:

- ``description_json``  — ProseMirror/Tiptap JSON snapshot.
- ``description_html``  — HTML render for read paths.
- ``description_binary`` — Yjs update bytes (``Doc.encodeStateAsUpdate``).
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .project import Project
    from .project_state import ProjectState


class WorkItemPriority(StrEnum):
    """Five-step priority scale.  ``none`` is the typed equivalent of NULL."""

    urgent = "urgent"
    high = "high"
    medium = "medium"
    low = "low"
    none = "none"


class WorkItem(BaseEntity):
    """A unit of work — issue, task, bug, story — owned by a project."""

    __tablename__ = "work_items"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "sequence_number",
            name="work_items_project_id_sequence_number_key",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    # Per-project human-friendly counter (``PRJ-123``).  Filled in by
    # ``actions.create`` under the unique constraint.
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_binary: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    priority: Mapped[WorkItemPriority] = mapped_column(
        StringEnum(WorkItemPriority, length=16),
        nullable=False,
        default=WorkItemPriority.none,
    )

    state_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project_states.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )

    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    start_date: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    target_date: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Float sort order — lets the UI drag-reorder without renumbering.
    sort_order: Mapped[float] = mapped_column(Float, nullable=False, default=65535.0)

    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    archived_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True
    )

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def state(cls) -> Mapped["ProjectState"]:
        return relationship("ProjectState", lazy="raise")
