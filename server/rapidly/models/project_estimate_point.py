"""Single value within a :class:`ProjectEstimate` scale.

``key`` is the canonical sort/identity (e.g. ``0``, ``1``, ``2``, ``3``,
``5``, ``8``, ``13``) while ``value`` is the rendered label
(``"0"``, ``"S"``, ``"4h"``, …).  The combination ``(estimate_id, key)``
is unique within a scale.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .project_estimate import ProjectEstimate


class ProjectEstimatePoint(BaseEntity):
    """A single labelled value inside an estimation scale."""

    __tablename__ = "project_estimate_points"
    __table_args__ = (
        UniqueConstraint(
            "estimate_id",
            "key",
            name="project_estimate_points_estimate_id_key_key",
        ),
    )

    estimate_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project_estimates.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    key: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    @declared_attr
    def estimate(cls) -> Mapped["ProjectEstimate"]:
        return relationship("ProjectEstimate", lazy="raise")
