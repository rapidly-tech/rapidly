"""Cycle (sprint) model: time-boxed container for work items inside a project.

A cycle gives a project a recurring cadence — typically 1-4 weeks — and
its membership is the set of work items expected to land before
``end_date``.  Work items keep their project as the primary owner and
join cycles through :class:`CycleWorkItem`; a single work item can
appear in zero or more cycles.

The action layer enforces ``start_date <= end_date``; the DB carries
nothing more than the column types so that historical dates remain
editable without migration friction.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project import Project
    from .user import User


class ProjectCycle(BaseEntity):
    """A time-boxed iteration inside a project."""

    __tablename__ = "project_cycles"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "name", name="project_cycles_project_id_name_key"
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    start_date: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    end_date: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True
    )

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def owner(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
