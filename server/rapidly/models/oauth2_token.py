"""OAuth2 access/refresh token pair issued to a client application.

Wraps the authlib ``OAuth2TokenMixin`` with Rapidly-specific scope
parsing, expiry calculation, and RFC 7662 introspection output.
"""

from typing import TYPE_CHECKING, Any, cast

from authlib.integrations.sqla_oauth2 import OAuth2TokenMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.identity.auth.scope import Scope, scope_to_set
from rapidly.identity.oauth2.sub_type import SubTypeModelMixin

if TYPE_CHECKING:
    from .oauth2_client import OAuth2Client


class OAuth2Token(BaseEntity, OAuth2TokenMixin, SubTypeModelMixin):
    """Persisted OAuth2 bearer token bound to a client and subject.

    The ``nonce`` column is indexed to support efficient PKCE replay
    detection across concurrent authorization flows.
    """

    __tablename__ = "oauth2_tokens"

    # -- Token columns -------------------------------------------------------

    client_id: Mapped[str] = mapped_column(String(72), nullable=False)
    nonce: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    # -- Client relationship -------------------------------------------------

    @declared_attr
    def client(cls) -> "Mapped[OAuth2Client]":
        return relationship(
            "OAuth2Client",
            primaryjoin="foreign(OAuth2Token.client_id) == OAuth2Client.client_id",
            viewonly=True,
            lazy="raise",
        )

    # -- Derived attributes --------------------------------------------------

    @property
    def expires_at(self) -> int:
        """Absolute epoch timestamp when this token expires."""
        return cast(int, self.issued_at) + cast(int, self.expires_in)

    @property
    def scopes(self) -> set[Scope]:
        """Parsed scope set for authorization checks."""
        return scope_to_set(cast(str, self.get_scope()))

    # -- RFC 7662 introspection ----------------------------------------------

    def get_introspection_data(self, issuer: str) -> dict[str, Any]:
        """Build the JSON body for a token introspection response."""
        is_active = not cast(bool, self.is_revoked()) and not cast(
            bool, self.is_expired()
        )
        return {
            "active": is_active,
            "client_id": self.client_id,
            "token_type": self.token_type,
            "scope": self.get_scope(),
            "sub_type": self.sub_type,
            "sub": str(self.sub.id),
            "aud": self.client_id,
            "iss": issuer,
            "exp": self.expires_at,
            "iat": self.issued_at,
        }
