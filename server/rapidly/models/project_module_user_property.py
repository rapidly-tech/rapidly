"""Per-user sticky view state on a project module.

Mirror of ``ProjectUserProperty`` (PR #714) targeting a module
instead of the project as a whole.  Plane equivalent:
``ModuleUserProperties``.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project_module import ProjectModule
    from .user import User


class ProjectModuleUserProperty(BaseEntity):
    """One row per (module, user) holding that user's view prefs."""

    __tablename__ = "project_module_user_properties"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "user_id",
            name="project_module_user_properties_module_id_user_id_key",
        ),
    )

    module_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project_modules.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    display_filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    display_properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    @declared_attr
    def module(cls) -> Mapped["ProjectModule"]:
        return relationship("ProjectModule", lazy="raise")

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
