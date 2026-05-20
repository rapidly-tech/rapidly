"""Per-user pinned note inside a workspace.

A ``Sticky`` is a personal scratchpad row — owned by a single user,
scoped to a workspace, never visible to anyone else.  Mirrors
Plane's ``Sticky``.

Why workspace-scoped rather than project-scoped: stickies typically
hold cross-project context ("doc links I keep returning to" /
"week's priorities") so binding them to one project would force
duplication.  The workspace is the natural scope.

Description is stored in three forms so the same rich-text editor
that powers comments / pages / work-items can drive stickies.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Float,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace


class Sticky(BaseEntity):
    """A personal note pinned inside a workspace."""

    __tablename__ = "stickies"

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_binary: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # 7-char (e.g. ``#f97316``) hex colour the UI uses as the sticky's
    # tile background. Nullable so the client can fall back to a
    # palette default.
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    # Float sort_order lets the UI drag-reorder without renumbering.
    sort_order: Mapped[float] = mapped_column(Float, nullable=False, default=65535.0)

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    @declared_attr
    def owner(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
