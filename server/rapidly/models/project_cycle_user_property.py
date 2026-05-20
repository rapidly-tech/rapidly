"""Per-user sticky view state on a project cycle.

Mirror of ``ProjectUserProperty`` (PR #714) targeting a cycle instead
of the project as a whole.  Plane equivalent: ``CycleUserProperties``.
The same JSON-opaque columns let the frontend evolve filter/display
schemas without migrations.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project_cycle import ProjectCycle
    from .user import User


class ProjectCycleUserProperty(BaseEntity):
    """One row per (cycle, user) holding that user's view prefs."""

    __tablename__ = "project_cycle_user_properties"
    __table_args__ = (
        UniqueConstraint(
            "cycle_id",
            "user_id",
            name="project_cycle_user_properties_cycle_id_user_id_key",
        ),
    )

    cycle_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project_cycles.id", ondelete="cascade"),
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
    def cycle(cls) -> Mapped["ProjectCycle"]:
        return relationship("ProjectCycle", lazy="raise")

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
