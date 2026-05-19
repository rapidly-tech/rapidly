"""External URL attached to a work item.

Distinct from ``WorkItemRelation`` (which links one work item to another):
``WorkItemLink`` points to an external resource — a Figma file, a PR, a
shared doc — so users can keep external context alongside the work item.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .user import User
    from .work_item import WorkItem


class WorkItemLink(BaseEntity):
    """External URL associated with a work item."""

    __tablename__ = "work_item_links"

    work_item_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")

    @declared_attr
    def created_by(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
