"""Registered OAuth2 client application.

Clients are created via dynamic registration (RFC 7591) and carry
credentials, metadata, and rate-limit configuration.  First-party
clients bypass consent screens; third-party clients require explicit
user authorisation.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from authlib.integrations.sqla_oauth2 import OAuth2ClientMixin
from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity, RateLimitMixin
from rapidly.identity.oauth2.sub_type import SubType

if TYPE_CHECKING:
    from rapidly.models import User


class OAuth2Client(RateLimitMixin, BaseEntity, OAuth2ClientMixin):
    """A registered application that may request tokens on behalf of users.

    The ``default_sub_type`` metadata field determines whether tokens
    issued to this client identify a user or a workspace by default.
    """

    __tablename__ = "oauth2_clients"
    __table_args__ = (UniqueConstraint("client_id"),)

    # -- Owner ---------------------------------------------------------------

    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="set null"), nullable=True, index=True
    )

    @declared_attr
    def user(cls) -> "Mapped[User | None]":
        return relationship("User", lazy="raise")

    # -- Credentials ---------------------------------------------------------

    client_id: Mapped[str] = mapped_column(String(72), nullable=False)
    client_secret: Mapped[str] = mapped_column(String(72), nullable=False)
    registration_access_token: Mapped[str] = mapped_column(
        String, index=True, nullable=False
    )

    # -- Flags ---------------------------------------------------------------

    first_party: Mapped[bool] = mapped_column(nullable=False, default=False)

    # -- Metadata helpers ----------------------------------------------------

    @property
    def default_sub_type(self) -> SubType:
        """The subject type to use when the authorization request omits one."""
        try:
            return SubType(self.client_metadata["default_sub_type"])
        except KeyError:
            return SubType.workspace
