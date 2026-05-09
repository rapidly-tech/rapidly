"""Active OAuth2 authorization grants.

A grant records that a user (or workspace) has authorised a specific
OAuth2 client with a given scope set.  Unique constraints ensure each
client has at most one grant per user and per workspace.
"""

from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.models.user import User
from rapidly.models.workspace import Workspace


class OAuth2Grant(BaseEntity):
    """Persisted consent record linking a client to a user or workspace."""

    __tablename__ = "oauth2_grants"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id"),
        UniqueConstraint("client_id", "workspace_id"),
    )

    # -- Client identifier ---------------------------------------------------

    client_id: Mapped[str] = mapped_column(String(72), nullable=False, index=True)

    # -- Authorised scope string ---------------------------------------------

    scope: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # -- Subject associations ------------------------------------------------

    user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )

    @declared_attr
    def user(cls) -> Mapped[User | None]:
        return relationship(User, lazy="joined")

    @declared_attr
    def workspace(cls) -> Mapped[Workspace | None]:
        return relationship(Workspace, lazy="joined")

    # -- Scope helpers -------------------------------------------------------

    @property
    def scopes(self) -> list[str]:
        """Parse the whitespace-delimited scope string into a list."""
        return self.scope.strip().split()
