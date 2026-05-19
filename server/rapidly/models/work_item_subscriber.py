"""A user's subscription to a work item.

A ``WorkItemSubscriber`` row means a user has opted in to receive
notifications about changes to a work item — state transitions,
comments, assignments — regardless of whether they're the assignee
or the author.  This mirrors Plane's ``IssueSubscriber``.

Why a separate model from ``WorkItemAssignee``:
- Assignment is a *role*; subscription is a *preference*. Removing an
  assignee shouldn't unsubscribe them, and someone who isn't an
  assignee should still be able to follow a work item.
- Notification fan-out is the *union* of assignees ∪ subscribers,
  so keeping the two distinct lets each evolve independently.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .user import User
    from .work_item import WorkItem


class WorkItemSubscriber(BaseEntity):
    """User who has opted into notifications for a work item."""

    __tablename__ = "work_item_subscribers"
    __table_args__ = (
        UniqueConstraint(
            "work_item_id",
            "user_id",
            name="work_item_subscribers_work_item_id_user_id_key",
        ),
    )

    work_item_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
