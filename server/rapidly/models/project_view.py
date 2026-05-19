"""Saved view (filter) model: named subsets of work items inside a project.

A view captures a set of filter criteria so a user can return to the
same slice of work items by clicking a saved name instead of
re-applying filters every time.  The ``filters`` JSON blob mirrors
the query parameters accepted by ``GET /api/work-items/`` — clients
hydrate the work-items list with the saved filters when navigating
to the view.

The shape is deliberately permissive: each filter key maps to a list
of values (or a single value for scalar fields like ``parent_id``).
Unknown keys are tolerated for forward-compatibility — older API
versions ignore them, newer versions can add filters without a
migration.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project import Project
    from .user import User


class ProjectView(BaseEntity):
    """A named filter over a project's work items."""

    __tablename__ = "project_views"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "name", name="project_views_project_id_name_key"
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

    # JSON blob mirroring ``GET /api/work-items/`` query params.  Validated
    # at the Pydantic layer; the DB only enforces shape.
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    archived_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True
    )

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def owner(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
