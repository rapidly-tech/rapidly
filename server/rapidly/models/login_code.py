"""ORM model for one-time passwordless login codes.

Each ``LoginCode`` row holds the SHA-256 hash of a short-lived code
that was emailed to the user.  The plaintext is never persisted.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CHAR, TIMESTAMP, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rapidly.core.db.models import BaseEntity

if TYPE_CHECKING:
    from rapidly.models import User

# SHA-256 hex digest length
_CODE_HASH_LENGTH = 64

# RFC-5321 maximum email length
_EMAIL_MAX_LENGTH = 320


class LoginCode(BaseEntity):
    """Stores a hashed one-time login code for passwordless authentication."""

    __tablename__ = "login_codes"

    code_hash: Mapped[str] = mapped_column(
        CHAR(_CODE_HASH_LENGTH), nullable=False, index=True, unique=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(_EMAIL_MAX_LENGTH), nullable=False, index=True
    )

    user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )
    user: Mapped["User | None"] = relationship("User", lazy="raise")
