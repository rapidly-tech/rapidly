"""Per-module roster.

A ``ProjectModuleMember`` is a join row that says "this user is on
this module."  Distinct from ``ProjectMember`` (project-wide
membership) and ``WorkItemAssignee`` (per-item assignment) — modules
sit between projects and work items, so they get their own roster
to represent who's *responsible* for the workstream as a whole.

Mirrors Plane's ``ModuleMember``.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project_module import ProjectModule
    from .user import User


class ProjectModuleMember(BaseEntity):
    """User assigned to a project module."""

    __tablename__ = "project_module_members"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "user_id",
            name="project_module_members_module_id_user_id_key",
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

    @declared_attr
    def module(cls) -> Mapped["ProjectModule"]:
        return relationship("ProjectModule", lazy="raise")

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
