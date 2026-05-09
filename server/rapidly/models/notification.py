"""In-app notification addressed to a dashboard user.

Each notification carries a ``type`` discriminator and a free-form
``payload`` JSONB blob whose schema depends on the type.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.types import JSONDict

if TYPE_CHECKING:
    from rapidly.models import User


class Notification(BaseEntity):
    """A single user-facing notification with a typed payload."""

    __tablename__ = "notifications"

    # -- Notification content ------------------------------------------------

    type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[JSONDict] = mapped_column(JSONB, nullable=False, default=dict)

    # -- Addressee -----------------------------------------------------------

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )

    user: Mapped["User"] = relationship("User", lazy="raise")
