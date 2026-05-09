"""Authenticated browser session for dashboard users.

Each session is bound to a hashed token stored in an HTTP-only cookie.
The ``scopes`` column restricts what the session may do (e.g. a
session created via a limited login flow may lack write scopes).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CHAR, TIMESTAMP, Boolean, ForeignKey, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.config import settings
from rapidly.core.db.models.base import BaseEntity
from rapidly.core.extensions.sqlalchemy import StringEnum
from rapidly.core.utils import now_utc
from rapidly.identity.auth.scope import Scope
from rapidly.models.user import User


def _default_expiry() -> datetime:
    """Compute the default session expiration from settings."""
    return now_utc() + settings.USER_SESSION_TTL


class UserSession(BaseEntity):
    """A single authenticated browser session backed by a hashed cookie token.

    Sessions carry an explicit scope list so different login flows
    (e.g. password-less vs full OAuth) can grant varying permission
    levels within the same session infrastructure.
    """

    __tablename__ = "user_sessions"

    # -- Session owner -------------------------------------------------------

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="cascade"), nullable=False
    )

    @declared_attr
    def user(cls) -> Mapped[User]:
        return relationship(User, lazy="joined")

    # -- Credentials and metadata --------------------------------------------

    token: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True, default=_default_expiry
    )
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)

    # -- Permission scopes ---------------------------------------------------

    scopes: Mapped[list[Scope]] = mapped_column(
        ARRAY(StringEnum(Scope)), nullable=False, default=list
    )

    # -- Impersonation -------------------------------------------------------

    is_impersonation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
