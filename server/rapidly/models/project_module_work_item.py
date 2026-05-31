"""Many-to-many join between modules and the work items they contain."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project_module import ProjectModule
    from .work_item import WorkItem


class ProjectModuleWorkItem(BaseEntity):
    """Membership of a work item in a module."""

    __tablename__ = "project_module_work_items"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "work_item_id",
            name="project_module_work_items_module_id_work_item_id_key",
        ),
    )

    module_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project_modules.id", ondelete="cascade"),
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
    def module(cls) -> Mapped["ProjectModule"]:
        return relationship("ProjectModule", lazy="raise")

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")
