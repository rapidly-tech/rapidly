"""An @mention edge from a comment to a mentioned user.

When the rich-text editor produces ``@alice`` in a comment, the
client records a ``WorkItemMention`` row so the backend can:
- fan out a notification to alice on comment create
- surface "comments where I'm mentioned" as a personal feed
- count unread mentions per work item

Why client-driven (not parsed server-side):
- The rich-text editor already resolves @-handles to user IDs at
  insert time; re-parsing on the server duplicates effort and
  introduces drift (the server might match a different user when
  multiple share a handle prefix).
- Keeps the backend free of an HTML/markdown parser that would
  have to evolve alongside the editor's serialisation.

The actual notification fan-out is out of scope for this PR — this
ships the model + endpoints; the notification hook can land later
on top of the #704 stack.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .user import User
    from .work_item_comment import WorkItemComment


class WorkItemMention(BaseEntity):
    """A user mentioned in a work-item comment."""

    __tablename__ = "work_item_mentions"
    __table_args__ = (
        UniqueConstraint(
            "comment_id",
            "mentioned_user_id",
            name="work_item_mentions_comment_id_mentioned_user_id_key",
        ),
    )

    comment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_item_comments.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    mentioned_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    mentioned_by_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    @declared_attr
    def comment(cls) -> Mapped["WorkItemComment"]:
        return relationship("WorkItemComment", lazy="raise")

    @declared_attr
    def mentioned_user(cls) -> Mapped["User"]:
        return relationship(
            "User",
            lazy="raise",
            foreign_keys="WorkItemMention.mentioned_user_id",
        )

    @declared_attr
    def mentioned_by(cls) -> Mapped["User | None"]:
        return relationship(
            "User",
            lazy="raise",
            foreign_keys="WorkItemMention.mentioned_by_id",
        )
