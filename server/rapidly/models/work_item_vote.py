"""Upvote / downvote on a work item.

A ``WorkItemVote`` is one user's signed vote on one work item — a
``+1`` upvote or a ``-1`` downvote.  Plane uses this in their public
deploy boards; for internal use it also makes a useful "priority
tiebreaker" signal.

Why ``Integer`` not ``CHECK(vote IN (-1, 1))``: the Pydantic layer
clamps the value at the API boundary (see ``types.WorkItemVoteCast``),
so a DB-level check would just duplicate the guarantee while making
a future "0 = retracted" state harder to add without a migration.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .user import User
    from .work_item import WorkItem


class WorkItemVote(BaseEntity):
    """A user's signed vote on a work item."""

    __tablename__ = "work_item_votes"
    __table_args__ = (
        UniqueConstraint(
            "work_item_id",
            "user_id",
            name="work_item_votes_work_item_id_user_id_key",
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
    vote: Mapped[int] = mapped_column(Integer, nullable=False)

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
