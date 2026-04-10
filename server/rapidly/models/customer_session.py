"""Bearer-token session granting a customer access to the portal.

A session is created when a customer authenticates via a login code
and expires after the configurable ``CUSTOMER_SESSION_TTL``.
"""

from datetime import datetime
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import CHAR, TIMESTAMP, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.config import settings
from rapidly.core.db.models.base import BaseEntity
from rapidly.core.utils import now_utc

from .customer import Customer


def _default_expiry() -> datetime:
    """Compute the expiration timestamp for a new session."""
    return now_utc() + settings.CUSTOMER_SESSION_TTL


class CustomerSession(BaseEntity):
    """Time-limited session token for the customer self-service portal.

    The ``raw_token`` transient attribute holds the unhashed token
    value immediately after creation -- it is never persisted.
    """

    __tablename__ = "customer_sessions"

    # -- Session credentials -------------------------------------------------

    token: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True, default=_default_expiry
    )

    # -- Optional return destination -----------------------------------------

    return_url: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    # -- Customer association ------------------------------------------------

    customer_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="cascade"), nullable=False, index=True
    )

    @declared_attr
    def customer(cls) -> Mapped[Customer]:
        return relationship(Customer, lazy="joined")

    # -- Transient raw token -------------------------------------------------

    @property
    def raw_token(self) -> str | None:
        return getattr(self, "_raw_token", None)

    @raw_token.setter
    def raw_token(self, value: str) -> None:
        self._raw_token = value

    # -- Portal deep-link URL ------------------------------------------------

    @property
    def customer_portal_url(self) -> str:
        """Construct the full portal URL with embedded session credentials."""
        params = urlencode(
            {"customer_session_token": self.raw_token, "email": self.customer.email}
        )
        workspace_slug = self.customer.workspace.slug
        return settings.generate_frontend_url(f"/{workspace_slug}/portal?{params}")
