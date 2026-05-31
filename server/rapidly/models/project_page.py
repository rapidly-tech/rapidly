"""Collaborative wiki page inside a project.

Pages form a hierarchy via ``parent_id``; the visibility flag splits
``private`` (owner only) from ``public`` (every project member).  The
description carriage is identical to ``WorkItem``: JSON + HTML + Yjs
binary, so the same Tiptap-on-Yjs editor stack can drive both work-item
descriptions and free-form pages.

The Yjs sync server itself is out of scope for this module — pages
ship today as CRUD over the static document.  When the sync server
lands, it will write ``description_binary`` from update bytes and the
HTML projection will be derived from there.
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    ForeignKey,
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
    from .user import User


class ProjectPageAccess(StrEnum):
    """Visibility scope inside the project.

    ``private`` — only the owner sees the page.
    ``public``  — every project member with read access sees it.
    """

    private = "private"
    public = "public"


class ProjectPage(BaseEntity):
    """A wiki/doc page belonging to a project."""

    __tablename__ = "project_pages"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "slug", name="project_pages_project_id_slug_key"
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
    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("project_pages.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)

    description_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_binary: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    access: Mapped[ProjectPageAccess] = mapped_column(
        StringEnum(ProjectPageAccess, length=16),
        nullable=False,
        default=ProjectPageAccess.public,
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    archived_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True
    )

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def owner(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
