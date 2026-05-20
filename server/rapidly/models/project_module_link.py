"""External URL attached to a project module.

Same shape as ``WorkItemLink`` (PR #701) but targets a module
instead of a work item.  Mirrors Plane's ``ModuleLink``.

Why a separate model from ``WorkItemLink``: keeps the FK cascade
correct on module deletion, and avoids a polymorphic parent_id
column that complicates queries.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project_module import ProjectModule
    from .user import User


class ProjectModuleLink(BaseEntity):
    """External URL associated with a project module."""

    __tablename__ = "project_module_links"

    module_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project_modules.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="set null"),
        nullable=True,
        index=True,
    )

    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    @declared_attr
    def module(cls) -> Mapped["ProjectModule"]:
        return relationship("ProjectModule", lazy="raise")

    @declared_attr
    def created_by(cls) -> Mapped["User | None"]:
        return relationship("User", lazy="raise")
