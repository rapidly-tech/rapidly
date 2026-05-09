"""ORM model for workspace-scoped API access tokens."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CHAR, TIMESTAMP, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity
from rapidly.identity.auth.scope import Scope, scope_to_set

from .workspace import Workspace


class WorkspaceAccessToken(BaseEntity):
    """Org-scoped API token with hash storage."""

    __tablename__ = "workspace_access_tokens"

    token: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, index=True
    )
    comment: Mapped[str] = mapped_column(String, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship(Workspace, lazy="raise")

    @property
    def scopes(self) -> set[Scope]:
        return scope_to_set(self.scope)
