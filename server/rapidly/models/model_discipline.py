"""Per-discipline element count for a federated model.

Populated by the IfcOpenShell worker once a model parses. Used by
the viewer chamber to render the "Architecture: 4,182 elements"
sidebar that helps coordinators sanity-check what's in a model
before opening it.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from .federated_model import FederatedModel


class ModelDiscipline(BaseEntity):
    """One row per discipline detected in a model."""

    __tablename__ = "model_disciplines"

    model_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("federated_models.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    # 'architecture', 'structure', 'MEP', 'civil', etc. Free-form
    # string; the worker extracts whatever IfcOpenShell's metadata
    # surfaces. No canonical enum because IFC's discipline tagging
    # is itself loose.
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    element_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @declared_attr
    def model(cls) -> Mapped["FederatedModel"]:
        return relationship("FederatedModel", lazy="raise")
