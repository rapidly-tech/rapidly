"""Module model: feature-scope workstream inside a project.

Where a :class:`ProjectCycle` is bound to a calendar window (sprint),
a :class:`ProjectModule` is bound to a deliverable.  Modules typically
span multiple cycles and stay open until the feature ships.

``ModuleStatus`` is a coarse lifecycle flag separate from the more
fine-grained work-item state machine — a module can be ``in_progress``
while only some of its work items are in started states.
"""

from datetime import datetime
from enum import StrEnum
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
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .project import Project
    from .user import User


class ModuleStatus(StrEnum):
    """High-level module lifecycle."""

    planned = "planned"
    in_progress = "in_progress"
    paused = "paused"
    completed = "completed"
    cancelled = "cancelled"


class ProjectModule(BaseEntity):
    """A workstream inside a project (e.g. "Billing v2")."""

    __tablename__ = "project_modules"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "name", name="project_modules_project_id_name_key"
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[ModuleStatus] = mapped_column(
        StringEnum(ModuleStatus, length=16),
        nullable=False,
        default=ModuleStatus.planned,
    )

    start_date: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    target_date: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True
    )

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def lead(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
