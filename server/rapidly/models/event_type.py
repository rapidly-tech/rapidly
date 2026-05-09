"""ORM model for named event type categories."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .workspace import Workspace


class EventType(BaseEntity):
    """Defines a named event category within an workspace."""

    __tablename__ = "event_types"
    __table_args__ = (
        UniqueConstraint(
            "name",
            name="event_types_name_workspace_id_key",
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    label_property_selector: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")
