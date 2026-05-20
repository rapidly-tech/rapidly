"""Per-project work-item type (Bug / Task / Story / Epic / …).

Plane's ``IssueType`` is workspace-scoped with a separate
``ProjectIssueType`` join.  We collapse that to a single project-scoped
table — matching the existing peers (``ProjectLabel``, ``ProjectState``)
which are also project-scoped.  If types ever need to be shared across
projects in a workspace, this can grow a ``workspace_id`` later.

``logo_props`` is opaque JSON owned by the frontend (icon name, colour
hex, etc.) so the backend stays neutral on visual presentation.
``is_epic`` flags the top-level "rolls up sub-work-items" type — kept as
a column so the UI can render epics specially without a string match
on ``name``.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Float,
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


class WorkItemType(BaseEntity):
    """A user-defined category of work item, scoped to one project."""

    __tablename__ = "work_item_types"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "name", name="work_item_types_project_id_name_key"
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Opaque JSON dictionary: icon name, colour, etc. The frontend owns
    # the schema so the backend doesn't need a migration each time
    # design adds a new presentation field.
    logo_props: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    is_epic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[float] = mapped_column(Float, nullable=False, default=65535.0)

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")
