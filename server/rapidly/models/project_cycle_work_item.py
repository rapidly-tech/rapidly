"""Many-to-many join between cycles and the work items they contain."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project_cycle import ProjectCycle
    from .work_item import WorkItem


class ProjectCycleWorkItem(BaseEntity):
    """Membership of a work item in a cycle."""

    __tablename__ = "project_cycle_work_items"
    __table_args__ = (
        UniqueConstraint(
            "cycle_id",
            "work_item_id",
            name="project_cycle_work_items_cycle_id_work_item_id_key",
        ),
    )

    cycle_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project_cycles.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    work_item_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def cycle(cls) -> Mapped["ProjectCycle"]:
        return relationship("ProjectCycle", lazy="raise")

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")
