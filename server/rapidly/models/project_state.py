"""Workflow state used by work items inside a project.

Each project owns its own ordered set of states (Backlog, Todo,
In Progress, Done, Cancelled, …).  States belong to one of six
:class:`StateGroup` buckets; the bucket determines reporting and
default behaviour even when teams rename the visible labels.
"""

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .project import Project


class StateGroup(StrEnum):
    """Coarse-grained bucket that determines reporting/funnel behaviour."""

    backlog = "backlog"
    unstarted = "unstarted"
    started = "started"
    completed = "completed"
    cancelled = "cancelled"
    triage = "triage"


class ProjectState(BaseEntity):
    """A renamable workflow state inside a single project."""

    __tablename__ = "project_states"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "name", name="project_states_project_id_name_key"
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#6b7280")
    group: Mapped[StateGroup] = mapped_column(
        StringEnum(StateGroup, length=16), nullable=False
    )
    # Float allows arbitrary insertions between existing states without renumbering.
    sequence: Mapped[float] = mapped_column(Float, nullable=False, default=1000.0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")
