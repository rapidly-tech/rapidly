"""Saved view (filter + display preset) for a project's work items.

A ``ProjectView`` captures the filter predicates, grouping, sort order
and visible columns a member wants to apply to the project's work-item
list.  Stored as opaque JSON — the schema is fully owned by the
frontend — so the backend stays neutral on what counts as a "filter"
or "display property" and can evolve without migrations.

Mirrors Plane's ``IssueView`` but always project-scoped for now;
workspace-scoped views can be added later if needed.
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
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .project import Project
    from .user import User


class ProjectViewAccess(StrEnum):
    """Visibility scope inside the project.

    ``private`` — only the owner sees the view.
    ``public``  — every project member with read access sees it.
    """

    private = "private"
    public = "public"


class ProjectView(BaseEntity):
    """A saved filter/display preset over a project's work items."""

    __tablename__ = "project_views"

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

    # Opaque JSON dictionaries — the schema lives in the frontend.
    # Keeping them backend-neutral lets us add new filter keys or
    # display properties without writing migrations.
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    display_filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    display_properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    access: Mapped[ProjectViewAccess] = mapped_column(
        StringEnum(ProjectViewAccess, length=16),
        nullable=False,
        default=ProjectViewAccess.public,
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[float] = mapped_column(Float, nullable=False, default=65535.0)

    archived_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True
    )

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def owner(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
