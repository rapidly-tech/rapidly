"""Per-user "favorite" shortcut.

A favorite is a typed pointer from a user to one of the project-domain
entities — project, cycle, module, page, or work item.  We deliberately
keep it polymorphic via ``(entity_type, entity_id)`` rather than five
nullable foreign keys: the table stays simple and the application
layer is the only place that needs to know which column means what.

Cascade-delete semantics are handled in the action layer.  When the
target entity is removed, the favorite row is soft-deleted by the same
worker that cleans up other orphans (out of scope for phase 1).
"""

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .user import User


class UserFavoriteEntityType(StrEnum):
    """Which project-domain shape this favorite points at."""

    project = "project"
    cycle = "cycle"
    module = "module"
    page = "page"
    work_item = "work_item"


class UserFavorite(BaseEntity):
    """A user's bookmark of a project-domain entity."""

    __tablename__ = "user_favorites"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "entity_type",
            "entity_id",
            name="user_favorites_user_id_entity_type_entity_id_key",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[UserFavoriteEntityType] = mapped_column(
        StringEnum(UserFavoriteEntityType, length=16),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
