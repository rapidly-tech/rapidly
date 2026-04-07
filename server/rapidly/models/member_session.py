"""ORM model for customer-portal member sessions.

Each ``MemberSession`` represents an authenticated portal session for a
specific team member, carrying a hashed bearer token and an expiry.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import CHAR, TIMESTAMP, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.config import settings
from rapidly.core.db.models.base import BaseEntity
from rapidly.core.utils import now_utc

if TYPE_CHECKING:
    from .customer import Customer

from .member import Member

MEMBER_SESSION_TOKEN_PREFIX = "rapidly_mst_"

# Length of the SHA-256 hex-encoded token stored in the DB.
_TOKEN_LENGTH = 64


def _default_expiry() -> datetime:
    """Compute the default expiration timestamp for a new session."""
    return now_utc() + settings.CUSTOMER_SESSION_TTL


class MemberSession(BaseEntity):
    """Bearer-token session for team member portal access."""

    __tablename__ = "member_sessions"

    token: Mapped[str] = mapped_column(CHAR(_TOKEN_LENGTH), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True, default=_default_expiry
    )
    return_url: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def member(cls) -> Mapped[Member]:
        return relationship(Member, lazy="joined")

    # -- raw token (set in memory after creation, never persisted) --

    @property
    def raw_token(self) -> str | None:
        return getattr(self, "_raw_token", None)

    @raw_token.setter
    def raw_token(self, value: str) -> None:
        self._raw_token = value

    # -- convenience accessors --

    @property
    def customer_id(self) -> UUID:
        return self.member.customer_id

    @property
    def customer(self) -> "Customer":
        return self.member.customer

    # -- portal URLs --

    def _portal_query_string(self, *, token_param: str) -> str:
        return urlencode({token_param: self.raw_token, "email": self.member.email})

    @property
    def member_portal_url(self) -> str:
        qs = self._portal_query_string(token_param="member_session_token")
        slug = self.member.customer.workspace.slug
        return settings.generate_frontend_url(f"/{slug}/portal?{qs}")

    @property
    def customer_portal_url(self) -> str:
        """API-compatible alias that uses the ``customer_session_token`` param."""
        qs = self._portal_query_string(token_param="customer_session_token")
        slug = self.member.customer.workspace.slug
        return settings.generate_frontend_url(f"/{slug}/portal?{qs}")
