"""Project model: workspace-scoped container for work items, cycles, modules, and pages.

A ``Project`` lives inside a single workspace and acts as the primary
unit of work organisation: every work item, cycle, module, view, and
page belongs to exactly one project.  Feature toggles let admins
selectively enable cycles, modules, views, pages, and intake.

The ``identifier`` is a short prefix (e.g. ``RAP``) that prefixes
work-item IDs in the UI (``RAP-123``); ``slug`` is used in URLs.
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity, RateLimitMixin
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace


class ProjectVisibility(StrEnum):
    """Whether the project is visible to all workspace members or invite-only."""

    private = "private"
    public = "public"


class Project(RateLimitMixin, BaseEntity):
    """A bounded space for work items, cycles, modules, pages, and views."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "identifier", name="projects_workspace_id_identifier_key"
        ),
        UniqueConstraint("workspace_id", "slug", name="projects_workspace_id_slug_key"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier: Mapped[str] = mapped_column(String(12), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    visibility: Mapped[ProjectVisibility] = mapped_column(
        StringEnum(ProjectVisibility, length=16),
        nullable=False,
        default=ProjectVisibility.private,
    )

    emoji: Mapped[str | None] = mapped_column(String(16), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Feature toggles (mirrors Plane's per-project module switches).
    is_cycles_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_modules_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_views_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_pages_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_intake_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    @declared_attr
    def owner(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
