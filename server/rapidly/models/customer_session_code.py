"""Short-lived numeric login code for customer portal authentication.

A code is generated and delivered (usually via e-mail) so the customer
can prove ownership of their address without a password.  Each code
expires after ``CUSTOMER_SESSION_CODE_TTL``.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CHAR, TIMESTAMP, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.config import settings
from rapidly.core.db.models.base import BaseEntity
from rapidly.core.utils import now_utc
from rapidly.models.customer import Customer


def _default_expiry() -> datetime:
    """Compute expiration time for a new login code."""
    return now_utc() + settings.CUSTOMER_SESSION_CODE_TTL


class CustomerSessionCode(BaseEntity):
    """A one-time login code sent to a customer's email address.

    The ``code`` column stores a hashed representation; the raw value
    is only available in-memory immediately after generation.
    """

    __tablename__ = "customer_session_codes"

    # -- Code and expiry -----------------------------------------------------

    code: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True, default=_default_expiry
    )

    # -- Addressee -----------------------------------------------------------

    email: Mapped[str] = mapped_column(String(320), nullable=False)

    # -- Customer association ------------------------------------------------

    customer_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="cascade"), nullable=False, index=True
    )

    @declared_attr
    def customer(cls) -> Mapped[Customer]:
        return relationship(Customer, lazy="joined")
