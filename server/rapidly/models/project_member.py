"""Project membership join with per-project role.

A ``ProjectMember`` records that a user belongs to a project at a
specific role.  Project roles are independent from workspace roles:
a workspace admin can still be a project guest, and vice versa.
"""

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .project import Project
    from .user import User


class ProjectMemberRole(StrEnum):
    """Project-scoped role.  Hierarchical: admin > member > guest."""

    admin = "admin"
    member = "member"
    guest = "guest"


class ProjectMember(BaseEntity):
    """Join row between a project and a user, with project-scoped role."""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "user_id", name="project_members_project_id_user_id_key"
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    role: Mapped[ProjectMemberRole] = mapped_column(
        StringEnum(ProjectMemberRole, length=16),
        nullable=False,
        default=ProjectMemberRole.member,
    )

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise")
