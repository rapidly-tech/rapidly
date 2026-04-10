"""Leaked authorization code revocation service.

When an external secret scanner reports a leaked authorization code,
this service soft-deletes the code so it can no longer be exchanged
for tokens.
"""

import structlog
from sqlalchemy import select

from rapidly.config import settings
from rapidly.core.crypto import get_token_hash
from rapidly.enums import TokenType
from rapidly.logging import Logger
from rapidly.models import OAuth2AuthorizationCode
from rapidly.postgres import AsyncSession

_log: Logger = structlog.get_logger()


class OAuth2AuthorizationCodeService:
    """Handle leaked authorization code detection and revocation."""

    async def revoke_leaked(
        self,
        session: AsyncSession,
        token: str,
        token_type: TokenType,
        *,
        notifier: str,
        url: str | None = None,
    ) -> bool:
        """Soft-delete a leaked authorization code.

        Returns True if the code was found, False otherwise.
        """
        code_hash = get_token_hash(token, secret=settings.SECRET)
        stmt = select(OAuth2AuthorizationCode).where(
            OAuth2AuthorizationCode.code == code_hash
        )
        result = await session.execute(stmt)
        auth_code = result.unique().scalar_one_or_none()

        if auth_code is None:
            return False

        auth_code.set_deleted_at()
        session.add(auth_code)

        _log.info(
            "Leaked authorization code invalidated",
            code_id=auth_code.id,
            notifier=notifier,
            url=url,
        )
        return True


oauth2_authorization_code = OAuth2AuthorizationCodeService()
