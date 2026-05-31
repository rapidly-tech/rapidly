"""Hierarchical tag attached to work items inside a project.

Labels are project-scoped today and may form a tree via ``parent_id``
(supports label groups such as "Bug › Critical").  A future migration
can promote labels to the workspace level by making ``project_id``
nullable; for now we keep the simpler model.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project import Project


class ProjectLabel(BaseEntity):
    """A coloured tag, optionally nested under a parent label."""

    __tablename__ = "project_labels"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "name", name="project_labels_project_id_name_key"
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("project_labels.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#6b7280")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")
