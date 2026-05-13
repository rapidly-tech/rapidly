"""Comment attached to a work item.

Comments carry both a JSON (Tiptap/ProseMirror) representation and an
HTML render so reading clients don't need to ship a renderer.  Edits
update both representations atomically.

Comments are owned by their author — only the author or a project
admin can mutate or delete a comment (enforced in
``rapidly.projects.comment.actions``).
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .user import User
    from .work_item import WorkItem


class WorkItemComment(BaseEntity):
    """A user-authored comment on a work item."""

    __tablename__ = "work_item_comments"

    work_item_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("work_items.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    body_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)

    @declared_attr
    def work_item(cls) -> Mapped["WorkItem"]:
        return relationship("WorkItem", lazy="raise")

    @declared_attr
    def actor(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
