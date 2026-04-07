"""Microsoft OAuth service: client factory, token exchange, and user info.

Provides the configured ``MicrosoftGraphOAuth2`` client, user-info fetching,
and account-linking helpers used by the Microsoft login routes.
"""

from typing import TypedDict

import httpx
import structlog
from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2
from httpx_oauth.oauth2 import OAuth2Token

from rapidly.config import settings
from rapidly.errors import RapidlyError
from rapidly.logging import Logger
from rapidly.models import OAuthAccount, User
from rapidly.models.user import OAuthPlatform
from rapidly.platform.user.oauth_service import oauth_account_service
from rapidly.platform.user.queries import UserRepository
from rapidly.platform.user.types import UserSignupAttribution
from rapidly.postgres import AsyncSession
from rapidly.worker import dispatch_task

_log: Logger = structlog.get_logger()

microsoft_oauth_client = MicrosoftGraphOAuth2(
    settings.MICROSOFT_CLIENT_ID,
    settings.MICROSOFT_CLIENT_SECRET,
    tenant=settings.MICROSOFT_TENANT,
)


class MicrosoftUserProfile(TypedDict):
    id: str
    email: str
    email_verified: bool
    display_name: str | None
    picture: str | None


class MicrosoftServiceError(RapidlyError): ...


class NoEmailError(MicrosoftServiceError):
    def __init__(self) -> None:
        super().__init__(
            "Your Microsoft account does not have an email address. "
            "Please add an email to your Microsoft account and try again."
        )


class CannotLinkUnverifiedEmailError(MicrosoftServiceError):
    def __init__(self, email: str) -> None:
        message = (
            f"An account already exists on Rapidly under the email {email}. "
            "We cannot automatically link it to your Microsoft account since "
            "this email address is not verified on Microsoft. "
            "Either verify your email address on Microsoft and try again "
            "or sign in using your email."
        )
        super().__init__(message, 403)


class AccountLinkedToAnotherUserError(MicrosoftServiceError):
    def __init__(self) -> None:
        message = (
            "This Microsoft account is already linked to another user on Rapidly. "
            "You may have already created another account "
            "with a different email address."
        )
        super().__init__(message, 403)


# ── Account resolution ──


async def get_updated_or_create(
    session: AsyncSession,
    *,
    token: OAuth2Token,
    signup_attribution: UserSignupAttribution | None = None,
) -> tuple[User, bool]:
    ms_profile = await _get_profile(token["access_token"])
    user_repository = UserRepository.from_session(session)
    user = await user_repository.get_by_oauth_account(
        OAuthPlatform.microsoft, ms_profile["id"]
    )

    if user is not None:
        oauth_account = user.get_oauth_account(OAuthPlatform.microsoft)
        if oauth_account is None:
            raise ValueError("Expected Microsoft OAuth account for existing user")
        oauth_account.access_token = token["access_token"]
        oauth_account.expires_at = token["expires_at"]
        oauth_account.account_username = ms_profile["display_name"]
        return (user, False)

    oauth_account = OAuthAccount(
        platform=OAuthPlatform.microsoft,
        account_id=ms_profile["id"],
        account_email=ms_profile["email"],
        account_username=ms_profile["display_name"],
        access_token=token["access_token"],
        expires_at=token["expires_at"],
    )

    user = await user_repository.get_by_email(ms_profile["email"])
    if user is not None:
        if ms_profile["email_verified"]:
            user.oauth_accounts.append(oauth_account)
            return (user, False)
        else:
            raise CannotLinkUnverifiedEmailError(ms_profile["email"])

    user = User(
        email=ms_profile["email"],
        email_verified=ms_profile["email_verified"],
        avatar_url=ms_profile["picture"],
        oauth_accounts=[oauth_account],
        signup_attribution=signup_attribution,
    )
    await user_repository.create(user, flush=True)

    dispatch_task("user.on_after_signup", user_id=user.id)

    return (user, True)


async def link_user(
    session: AsyncSession,
    *,
    user: User,
    token: OAuth2Token,
) -> User:
    ms_profile = await _get_profile(token["access_token"])

    oauth_account = await oauth_account_service.get_by_platform_and_account_id(
        session, OAuthPlatform.microsoft, ms_profile["id"]
    )
    if oauth_account is not None:
        if oauth_account.user_id != user.id:
            raise AccountLinkedToAnotherUserError()
    else:
        oauth_account = OAuthAccount(
            platform=OAuthPlatform.microsoft,
            account_id=ms_profile["id"],
            account_email=ms_profile["email"],
        )
        user.oauth_accounts.append(oauth_account)
        _log.info(
            "oauth_account.connect",
            user_id=user.id,
            platform="microsoft",
            account_email=ms_profile["email"],
        )

    oauth_account.access_token = token["access_token"]
    oauth_account.expires_at = token["expires_at"]
    oauth_account.account_username = ms_profile["display_name"]

    await session.flush()

    return user


# ── Profile sync ──


async def _get_profile(token: str) -> MicrosoftUserProfile:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()

        data = response.json()
        email = data.get("mail") or data.get("userPrincipalName") or ""

        if not email:
            raise NoEmailError()

        # Microsoft requires email verification during account registration,
        # so emails from the Graph API are considered verified.
        return {
            "id": data["id"],
            "email": email,
            "email_verified": True,
            "display_name": data.get("displayName"),
            "picture": None,
        }
