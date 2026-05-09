"""OAuth2 token persistence and leak-response service.

Handles hash-based access-token look-up, revocation status checks, and
the complete leak-response workflow (revoke + email notification) when a
token is reported by an external secret scanner.
"""

import time
from typing import cast

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from rapidly.config import settings
from rapidly.core.crypto import get_token_hash
from rapidly.enums import TokenType
from rapidly.logging import Logger
from rapidly.messaging.email.react import render_email_template
from rapidly.messaging.email.sender import enqueue_email
from rapidly.messaging.email.types import OAuth2LeakedTokenEmail, OAuth2LeakedTokenProps
from rapidly.models import OAuth2Token, User
from rapidly.platform.workspace_membership import (
    actions as workspace_membership_service,
)
from rapidly.postgres import AsyncSession

_log: Logger = structlog.get_logger()


def _hash_token(raw: str) -> str:
    """Compute the storage hash for a raw token string."""
    return get_token_hash(raw, secret=settings.SECRET)


class OAuth2TokenService:
    """Access-token look-up, validation, and leak revocation."""

    async def get_by_access_token(
        self, session: AsyncSession, access_token: str
    ) -> OAuth2Token | None:
        """Find a non-revoked, authenticable token by its raw access-token value."""
        stmt = (
            select(OAuth2Token)
            .where(OAuth2Token.access_token == _hash_token(access_token))
            .options(joinedload(OAuth2Token.client))
        )
        result = await session.execute(stmt)
        record = result.unique().scalar_one_or_none()

        if record is None:
            return None
        if cast(bool, record.is_revoked()):
            return None
        if not record.sub.can_authenticate:
            return None
        return record

    async def revoke_leaked(
        self,
        session: AsyncSession,
        token: str,
        token_type: TokenType,
        *,
        notifier: str,
        url: str | None = None,
    ) -> bool:
        """Revoke a leaked token and notify affected parties by email.

        Returns True if the token was found (whether freshly revoked or
        already revoked), False if the token doesn't exist.
        """
        stmt = select(OAuth2Token).options(
            joinedload(OAuth2Token.user),
            joinedload(OAuth2Token.workspace),
            joinedload(OAuth2Token.client),
        )
        hashed = _hash_token(token)
        if token_type == TokenType.access_token:
            stmt = stmt.where(OAuth2Token.access_token == hashed)
        elif token_type == TokenType.refresh_token:
            stmt = stmt.where(OAuth2Token.refresh_token == hashed)
        else:
            raise ValueError(f"Cannot revoke token_type={token_type!r}")

        result = await session.execute(stmt)
        leaked_token = result.unique().scalar_one_or_none()

        if leaked_token is None:
            return False
        if cast(bool, leaked_token.is_revoked()):
            return True  # already revoked -- idempotent

        # Revoke both halves
        now_epoch = int(time.time())
        leaked_token.access_token_revoked_at = now_epoch  # pyright: ignore
        leaked_token.refresh_token_revoked_at = now_epoch  # pyright: ignore
        session.add(leaked_token)

        # Build recipient list
        affected_subject = leaked_token.sub
        if isinstance(affected_subject, User):
            email_addrs = [affected_subject.email]
        else:
            members = await workspace_membership_service.list_by_workspace(
                session, affected_subject.id
            )
            email_addrs = [m.user.email for m in members]

        # Send notification emails
        client_name = cast(str, leaked_token.client.client_name)
        for addr in email_addrs:
            html = render_email_template(
                OAuth2LeakedTokenEmail(
                    props=OAuth2LeakedTokenProps(
                        email=addr,
                        client_name=client_name,
                        notifier=notifier,
                        url=url or "",
                    )
                )
            )
            enqueue_email(
                to_email_addr=addr,
                subject="Security Notice - Your Rapidly Access Token has been leaked",
                html_content=html,
            )

        _log.info(
            "Leaked token revoked",
            token_id=leaked_token.id,
            token_type=token_type,
            notifier=notifier,
            url=url,
        )
        return True


oauth2_token = OAuth2TokenService()
