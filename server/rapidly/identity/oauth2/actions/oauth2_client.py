"""OAuth2 client management and leak-response service.

Provides paginated client listing, client-id look-up, and the
leak-response workflow (secret rotation + email notification) for
client secrets and registration tokens reported by external scanners.
"""

from collections.abc import Sequence
from typing import cast

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from rapidly.core.crypto import generate_token
from rapidly.core.pagination import PaginationParams, paginate
from rapidly.enums import TokenType
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.logging import Logger
from rapidly.messaging.email.react import render_email_template
from rapidly.messaging.email.sender import enqueue_email
from rapidly.messaging.email.types import (
    OAuth2LeakedClientEmail,
    OAuth2LeakedClientProps,
)
from rapidly.models import OAuth2Client, User
from rapidly.postgres import AsyncSession

from ..constants import CLIENT_REGISTRATION_TOKEN_PREFIX, CLIENT_SECRET_PREFIX

_log: Logger = structlog.get_logger()

# Maps token types to the email subject line and the field to rotate
_LEAK_HANDLERS: dict[TokenType, tuple[str, str]] = {
    TokenType.client_secret: (
        "Security Notice - Your Rapidly OAuth2 Client Secret has been leaked",
        "client_secret",
    ),
    TokenType.client_registration_token: (
        "Security Notice - Your Rapidly OAuth2 Client Registration Token has been leaked",
        "registration_access_token",
    ),
}


class OAuth2ClientService:
    """Client registration, look-up, and leak handling."""

    async def list(
        self,
        session: AsyncSession,
        auth_subject: AuthPrincipal[User],
        *,
        pagination: PaginationParams,
    ) -> tuple[Sequence[OAuth2Client], int]:
        """Return the caller's non-deleted clients, newest first."""
        stmt = (
            select(OAuth2Client)
            .where(
                OAuth2Client.user_id == auth_subject.subject.id,
                OAuth2Client.deleted_at.is_(None),
            )
            .order_by(OAuth2Client.created_at.desc())
        )
        return await paginate(session, stmt, pagination=pagination)

    async def get_by_client_id(
        self, session: AsyncSession, client_id: str
    ) -> OAuth2Client | None:
        """Look up a non-deleted client by its public ``client_id``."""
        stmt = select(OAuth2Client).where(
            OAuth2Client.client_id == client_id,
            OAuth2Client.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_leaked(
        self,
        session: AsyncSession,
        token: str,
        token_type: TokenType,
        *,
        notifier: str,
        url: str | None = None,
    ) -> bool:
        """Rotate a leaked client credential and notify the owner.

        Returns True if the client was found, False otherwise.
        """
        stmt = select(OAuth2Client).options(joinedload(OAuth2Client.user))
        if token_type == TokenType.client_secret:
            stmt = stmt.where(OAuth2Client.client_secret == token)
        elif token_type == TokenType.client_registration_token:
            stmt = stmt.where(OAuth2Client.registration_access_token == token)
        else:
            raise ValueError(f"Cannot handle token_type={token_type!r}")

        result = await session.execute(stmt)
        client = result.unique().scalar_one_or_none()
        if client is None:
            return False

        # Rotate the compromised credential
        handler = _LEAK_HANDLERS.get(token_type)
        assert handler is not None
        email_subject, field_name = handler

        if field_name == "client_secret":
            client.client_secret = generate_token(prefix=CLIENT_SECRET_PREFIX)  # pyright: ignore
        else:
            client.registration_access_token = generate_token(
                prefix=CLIENT_REGISTRATION_TOKEN_PREFIX
            )
        session.add(client)

        # Notify the owning user
        if client.user is not None:
            owner_email = client.user.email
            html = render_email_template(
                OAuth2LeakedClientEmail(
                    props=OAuth2LeakedClientProps(
                        email=owner_email,
                        token_type=token_type,
                        client_name=cast(str, client.client_name),
                        notifier=notifier,
                        url=url or "",
                    )
                )
            )
            enqueue_email(
                to_email_addr=owner_email,
                subject=email_subject,
                html_content=html,
            )

        _log.info(
            "Leaked client credential rotated",
            client_id=client.id,
            token_type=token_type,
            notifier=notifier,
            url=url,
        )
        return True


oauth2_client = OAuth2ClientService()
