"""Immutable snapshot of a project page's content.

A new ``ProjectPageVersion`` row is written each time a page's
``name``, ``description_json`` or ``description_html`` is updated.
The row captures the *previous* state (so reading version N gives you
the page as it looked before edit N+1).  Versions are append-only —
the page submodule never updates or deletes them, only inserts.

Why store ``name`` too: page renames are part of the page's revision
history.  Without snapshotting ``name``, "restore this version" can't
reconstruct the page's earlier display title.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project_page import ProjectPage
    from .user import User


class ProjectPageVersion(BaseEntity):
    """Append-only snapshot of a project page's content at a point in time."""

    __tablename__ = "project_page_versions"
    __table_args__ = (
        UniqueConstraint(
            "page_id",
            "version_number",
            name="project_page_versions_page_id_version_number_key",
        ),
    )

    page_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project_pages.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    # 1-based, monotonically increasing within a single page.  Computed
    # in actions.py via ``max(version_number) + 1`` under the same
    # transaction as the page update so there are no gaps.
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    @declared_attr
    def page(cls) -> Mapped["ProjectPage"]:
        return relationship("ProjectPage", lazy="raise")

    @declared_attr
    def author(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
