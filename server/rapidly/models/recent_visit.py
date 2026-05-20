"""Per-user "recently visited" feed.

Each time a user opens an entity (project / work item / page / cycle
/ module / view), the client records a ``RecentVisit`` row.  Subsequent
visits to the same entity bump ``visited_at`` rather than insert a
new row, so the feed is a running list of distinct entities ordered
by last touch.

Why a polymorphic ``entity_type`` + ``entity_id`` instead of one FK
column per type: the "recents" feed is naturally heterogeneous —
projects, work items, and pages live in the same list — and a join
column per type would explode into seven nullable FKs.  The trade-
off is referential integrity: cascade behaviour is enforced at the
application layer (the routes that delete entities don't bother
sweeping recents because stale rows just resolve to 404 client-side).
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace


class RecentVisitEntityType(StrEnum):
    """The kinds of rows that can appear in the recents feed."""

    project = "project"
    work_item = "work_item"
    page = "page"
    cycle = "cycle"
    module = "module"
    view = "view"


class RecentVisit(BaseEntity):
    """A user's most-recent touch of a specific entity."""

    __tablename__ = "recent_visits"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "entity_type",
            "entity_id",
            name="recent_visits_user_entity_key",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[RecentVisitEntityType] = mapped_column(
        StringEnum(RecentVisitEntityType, length=16),
        nullable=False,
    )
    # No FK: the polymorphic ``entity_id`` can target many tables.
    # Stale rows after an entity is deleted are tolerated (see module
    # docstring).
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)

    visited_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True
    )

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")
