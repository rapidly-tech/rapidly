"""User HTTP endpoints: profile, scopes, identity verification, and account deletion.

Provides endpoints for reading/updating the authenticated user's profile,
managing OAuth account connections, requesting identity verification,
and initiating account deletion.
"""

from fastapi import Depends

from rapidly.identity.auth.dependencies import WebUserRead, WebUserWrite
from rapidly.models import User
from rapidly.models.user import OAuthPlatform
from rapidly.openapi import APITag
from rapidly.platform.user import actions as user_service
from rapidly.platform.user.oauth_service import oauth_account_service
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

from .permissions import UserScopesRead, UserWrite
from .types import (
    UserDeletionResponse,
    UserIdentityVerification,
    UserRead,
    UserScopes,
)

router = APIRouter(prefix="/users", tags=["users", APITag.private])


# ---------------------------------------------------------------------------
# OAuth management
# ---------------------------------------------------------------------------


@router.delete(
    "/me/oauth-accounts/{platform}",
    status_code=204,
    responses={
        404: {"description": "OAuth account not found"},
        400: {"description": "Cannot disconnect last authentication method"},
    },
)
async def disconnect_oauth_account(
    platform: OAuthPlatform,
    auth_subject: WebUserWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Disconnect an OAuth account (Microsoft or Google) from the authenticated user.

    This allows users to unlink their OAuth provider while keeping their Rapidly account.
    They can still authenticate using other methods (email magic link or other OAuth providers).

    Note: You cannot disconnect your last authentication method if your email is not verified.
    """
    await oauth_account_service.disconnect_platform(
        session, auth_subject.subject, platform
    )


# ---------------------------------------------------------------------------
# Account deletion
# ---------------------------------------------------------------------------


@router.delete(
    "/me",
    response_model=UserDeletionResponse,
    responses={
        200: {"description": "Deletion result"},
    },
)
async def delete_authenticated_user(
    auth_subject: UserWrite,
    session: AsyncSession = Depends(get_db_session),
) -> UserDeletionResponse:
    """
    Delete the authenticated user account.

    A user can only be deleted if all workspaces they are members of have been
    deleted first. If the user has active workspaces, the response will include
    the list of workspaces that must be deleted before the user account can be
    removed.

    When deleted:
    - User's email is anonymized
    - User's avatar and metadata are cleared
    - User's OAuth accounts are deleted (cascade)
    - User's Account (payout account) is deleted if present
    """
    return await user_service.request_deletion(session, auth_subject.subject)


# ---------------------------------------------------------------------------
# Profile & verification
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserRead)
async def get_authenticated(auth_subject: WebUserRead) -> User:
    return auth_subject.subject


@router.get("/me/scopes", response_model=UserScopes)
async def scopes(
    auth_subject: UserScopesRead,
) -> UserScopes:
    return UserScopes(scopes=list(auth_subject.scopes))


@router.post(
    "/me/identity-verification",
    response_model=UserIdentityVerification,
    status_code=201,
)
async def create_identity_verification(
    auth_subject: WebUserWrite,
    session: AsyncSession = Depends(get_db_session),
) -> UserIdentityVerification:
    return await user_service.create_identity_verification(
        session, user=auth_subject.subject
    )
