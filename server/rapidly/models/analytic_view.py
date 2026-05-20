"""Saved analytics dashboard configuration.

An ``AnalyticView`` is a *named, shareable* analytics query that the
dashboard layer can re-render on demand.  It does NOT store the
computed results — those are recomputed each time the query is run
against current data.  Mirrors Plane's ``AnalyticView``.

Why workspace-scoped, project-optional: many useful analytics span
all projects ("which assignees are most-loaded this sprint?") and a
view that's pinned to a single project can't grow into a workspace-
wide one without losing its history.  The optional ``project_id``
lets callers narrow the same view to one project when needed.

``query`` is opaque JSON — the schema lives entirely in the frontend,
so adding new chart kinds or filter axes doesn't need a migration.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project import Project
    from .user import User
    from .workspace import Workspace


class AnalyticView(BaseEntity):
    """A saved analytics dashboard configuration."""

    __tablename__ = "analytic_views"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    # Optional — when set, the view is scoped to one project; when null,
    # it spans every project in the workspace.
    project_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Opaque query dict — chart kind, metric, dimensions, filters.
    # Backend stays neutral; analytics submodule renders the result
    # when the frontend asks.
    query: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    @declared_attr
    def project(cls) -> Mapped["Project | None"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def created_by(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
