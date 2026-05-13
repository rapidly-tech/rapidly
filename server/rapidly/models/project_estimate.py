"""Estimation system attached to a project.

A project can define multiple estimation systems (story points, t-shirt
sizes, time-based), but only one is active at a time.  Individual scale
values are stored in :class:`ProjectEstimatePoint`.
"""

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum

if TYPE_CHECKING:
    from .project import Project


class EstimateType(StrEnum):
    """Display style for estimate points."""

    points = "points"
    categories = "categories"
    time = "time"


class ProjectEstimate(BaseEntity):
    """A named estimation scale (e.g. Fibonacci, T-Shirt) inside a project."""

    __tablename__ = "project_estimates"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "name", name="project_estimates_project_id_name_key"
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    type: Mapped[EstimateType] = mapped_column(
        StringEnum(EstimateType, length=16),
        nullable=False,
        default=EstimateType.points,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @declared_attr
    def project(cls) -> Mapped["Project"]:
        return relationship("Project", lazy="raise")
