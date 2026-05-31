"""Join row between a work item and a project label."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project_label import ProjectLabel
    from .work_item import WorkItem


class WorkItemLabel(BaseEntity):
    """A label applied to a work item."""

    __tablename__ = "work_item_labels"
    __table_args__ = (
        UniqueConstraint(
            "work_item_id",
            "label_id",
            name="work_item_labels_work_item_id_label_id_key",
        ),
    )

    work_item_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    label_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project_labels.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")

    @declared_attr
    def label(cls) -> Mapped["ProjectLabel"]:
        return relationship("ProjectLabel", lazy="raise")
