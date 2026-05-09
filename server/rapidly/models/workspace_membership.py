"""ORM model for user-to-workspace membership."""

from uuid import UUID

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import AuditableModel
from rapidly.models.user import User
from rapidly.models.workspace import Workspace


class WorkspaceMembership(AuditableModel):
    """Tracks membership of a user within an workspace."""

    __tablename__ = "workspace_memberships"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        primary_key=True,
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )

    @declared_attr
    def user(cls) -> "Mapped[User]":
        return relationship("User", lazy="raise")

    @declared_attr
    def workspace(cls) -> "Mapped[Workspace]":
        return relationship("Workspace", lazy="raise")
