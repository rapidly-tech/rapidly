"""Pending email-change verification token.

When a user requests an email change, a verification record is
created with a hashed token and a TTL.  Confirming the token
completes the address update.
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.config import settings
from rapidly.core.db.models import BaseEntity
from rapidly.core.utils import now_utc
from rapidly.models.user import User


def _default_expiry() -> datetime:
    """Compute expiration timestamp for a new verification token."""
    return now_utc() + timedelta(seconds=settings.EMAIL_VERIFICATION_TTL_SECONDS)


class EmailVerification(BaseEntity):
    """A time-limited token that proves ownership of a new email address."""

    __tablename__ = "email_verification"

    # -- User association ----------------------------------------------------

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="cascade"), nullable=False
    )

    @declared_attr
    def user(cls) -> Mapped[User]:
        return relationship(User)

    # -- Verification data ---------------------------------------------------

    email: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_default_expiry
    )
