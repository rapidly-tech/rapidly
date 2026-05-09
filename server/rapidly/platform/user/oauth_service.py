"""User OAuth account linking service.

Handles creation, look-up, and disconnection of ``OAuthAccount``
records that associate third-party OAuth tokens (Microsoft, Google,
Discord) with Rapidly users.
"""

import structlog

from rapidly.errors import RapidlyError
from rapidly.logging import Logger
from rapidly.models import OAuthAccount, User
from rapidly.models.user import OAuthPlatform
from rapidly.platform.user.queries import OAuthAccountRepository
from rapidly.postgres import AsyncSession

_log: Logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OAuthError(RapidlyError): ...


class OAuthAccountNotFound(OAuthError):
    def __init__(self, platform: OAuthPlatform) -> None:
        self.platform = platform
        super().__init__(f"No {platform} OAuth account found for this user.", 404)


class CannotDisconnectLastAuthMethod(OAuthError):
    def __init__(self) -> None:
        super().__init__(
            "Cannot disconnect this OAuth account as it's your only authentication method. "
            "Please verify your email or connect another OAuth provider before disconnecting.",
            400,
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class OAuthAccountService:
    async def get_by_platform_and_account_id(
        self, session: AsyncSession, platform: OAuthPlatform, account_id: str
    ) -> OAuthAccount | None:
        repo = OAuthAccountRepository.from_session(session)
        return await repo.get_by_platform_and_account_id(platform, account_id)

    async def disconnect_platform(
        self, session: AsyncSession, user: User, platform: OAuthPlatform
    ) -> None:
        """Remove all OAuth accounts for *platform* from *user*.

        Raises ``OAuthAccountNotFound`` if the platform isn't linked, and
        ``CannotDisconnectLastAuthMethod`` if disconnecting would leave
        the user with no way to log in.
        """
        repo = OAuthAccountRepository.from_session(session)

        # Fetch all accounts for this platform (some users have duplicates)
        target_accounts = await repo.get_all_by_user_and_platform(user.id, platform)
        if not target_accounts:
            raise OAuthAccountNotFound(platform)

        # Ensure at least one other auth method remains
        remaining = await repo.count_by_user_excluding(
            user.id, exclude_ids=[a.id for a in target_accounts]
        )
        if remaining == 0 and not user.email_verified:
            raise CannotDisconnectLastAuthMethod()

        for acct in target_accounts:
            await repo.delete(acct)
            _log.info(
                "oauth_account.disconnect",
                oauth_account_id=acct.id,
                platform=platform,
            )
        await session.flush()


oauth_account_service = OAuthAccountService()
