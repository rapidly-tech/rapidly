"""Emoji reaction on a work-item comment.

Shape mirrors ``WorkItemReaction`` exactly but targets a comment row
instead of the work item itself.  Kept as a separate model (rather
than a polymorphic ``parent_id``) so the foreign-key cascade behaves
cleanly when comments are hard-deleted, and so the queries can stay
type-safe without runtime discrimination.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .user import User
    from .work_item_comment import WorkItemComment


class WorkItemCommentReaction(BaseEntity):
    """A user's emoji reaction on a work-item comment."""

    __tablename__ = "work_item_comment_reactions"
    __table_args__ = (
        UniqueConstraint(
            "comment_id",
            "user_id",
            "reaction",
            name="work_item_comment_reactions_comment_id_user_id_reaction_key",
        ),
    )

    comment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_item_comments.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    reaction: Mapped[str] = mapped_column(String(32), nullable=False)

    @declared_attr
    def comment(cls) -> Mapped["WorkItemComment"]:
        return relationship("WorkItemComment", lazy="raise")

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
