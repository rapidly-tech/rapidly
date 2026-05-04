"""ORM model for OAuth2 authorization codes."""

from authlib.integrations.sqla_oauth2 import (
    OAuth2AuthorizationCodeMixin,
)
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from rapidly.core.db.models import BaseEntity
from rapidly.identity.oauth2.sub_type import SubTypeModelMixin


class OAuth2AuthorizationCode(
    BaseEntity, SubTypeModelMixin, OAuth2AuthorizationCodeMixin
):
    """Issued authorization code pending exchange for an access token."""

    __tablename__ = "oauth2_authorization_codes"

    client_id: Mapped[str] = mapped_column(String(72), nullable=False)
