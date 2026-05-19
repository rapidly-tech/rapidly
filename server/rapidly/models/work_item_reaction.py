"""Emoji reaction on a work item.

A row per (user, work_item, emoji) tuple — unique so the same user
can't double-tap the same emoji on the same item, but can leave
multiple different emojis on one item.

The ``reaction`` column stores the literal emoji (UTF-8 codepoint
sequence) rather than a normalised shortcode like ``:thumbsup:``.
Why: lets the client pick any emoji the platform supports without
the backend keeping an allowlist that drifts with each Unicode
release.  Length is capped at 32 bytes to leave room for ZWJ
sequences while preventing arbitrary text.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .user import User
    from .work_item import WorkItem


class WorkItemReaction(BaseEntity):
    """A user's emoji reaction on a work item."""

    __tablename__ = "work_item_reactions"
    __table_args__ = (
        UniqueConstraint(
            "work_item_id",
            "user_id",
            "reaction",
            name="work_item_reactions_work_item_id_user_id_reaction_key",
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
    reaction: Mapped[str] = mapped_column(String(32), nullable=False)

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
