"""Per-user sticky view state on a project.

A ``ProjectUserProperty`` row stores the filter, display, and column
preferences a single user has chosen for one project's work-item
list, so when they return the project opens in the view state they
left it.  Mirrors Plane's ``ProjectUserProperty``.

Why this is separate from ``ProjectView`` (#702):
- ``ProjectView`` is a *named, shareable* preset that anyone in the
  project can apply.  This model is a single *implicit* per-user
  state that gets upserted on every UI change.
- The data lives outside any view's lifecycle — switching to a
  different view doesn't erase your preferred display properties.

JSON columns are intentionally opaque so the frontend can evolve
the schema (new filter keys, new display props) without migrations.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project import Project
    from .user import User


class ProjectUserProperty(BaseEntity):
    """One row per (project, user) holding that user's view prefs."""

    __tablename__ = "project_user_properties"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "user_id",
            name="project_user_properties_project_id_user_id_key",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    display_filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    display_properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
