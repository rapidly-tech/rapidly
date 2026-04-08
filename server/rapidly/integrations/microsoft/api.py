"""Microsoft OAuth endpoints: login initiation and account linking.

Manages the Microsoft OAuth2 redirect flow for user authentication,
including state-cookie management and account linking with existing
Rapidly user records.
"""

import uuid
from typing import Any

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback
from httpx_oauth.oauth2 import OAuth2Token

from rapidly.core.http import ReturnTo, get_safe_return_url
from rapidly.core.oauth import (
    OAuthCallbackError,
    clear_login_cookie,
    create_authorization_response,
    validate_callback,
)
from rapidly.identity.auth import actions as auth_service
from rapidly.identity.auth.dependencies import WebUserOrAnonymous, WebUserWrite
from rapidly.identity.auth.models import is_user_principal
from rapidly.openapi import APITag
from rapidly.platform.user.types import (
    UserSignupAttribution,
    UserSignupAttributionQuery,
)
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.posthog import posthog
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from . import actions as microsoft_service
from .actions import MicrosoftServiceError, microsoft_oauth_client

# ---------------------------------------------------------------------------
# OAuth2 callback dependencies
# ---------------------------------------------------------------------------

oauth2_login_authorize_callback = OAuth2AuthorizeCallback(
    microsoft_oauth_client, route_name="integrations.microsoft.login.callback"
)
oauth2_link_authorize_callback = OAuth2AuthorizeCallback(
    microsoft_oauth_client, route_name="integrations.microsoft.link.callback"
)

_MICROSOFT_SCOPES = [
    "openid",
    "profile",
    "email",
    "User.Read",
]


# ---------------------------------------------------------------------------
# Shared authorization helper
# ---------------------------------------------------------------------------


async def create_microsoft_authorization_response(
    request: Request,
    redis: Redis,
    state: dict[str, Any],
    callback_route: str,
) -> RedirectResponse:
    return await create_authorization_response(
        request=request,
        redis=redis,
        state=state,
        callback_route=callback_route,
        oauth_client=microsoft_oauth_client,
        scopes=_MICROSOFT_SCOPES,
        type="microsoft",
    )


# ---------------------------------------------------------------------------
# Login sub-router
# ---------------------------------------------------------------------------

login_router = APIRouter(
    prefix="/login",
    tags=["integrations_microsoft_login", APITag.private],
)


@login_router.get("/authorize", name="integrations.microsoft.login.authorize")
async def login_authorize(
    request: Request,
    auth_subject: WebUserOrAnonymous,
    return_to: ReturnTo,
    signup_attribution: UserSignupAttributionQuery,
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    if is_user_principal(auth_subject):
        return RedirectResponse(get_safe_return_url(return_to), 303)

    state: dict[str, Any] = {"return_to": return_to}
    if signup_attribution:
        state["signup_attribution"] = signup_attribution.model_dump(exclude_unset=True)

    return await create_microsoft_authorization_response(
        request, redis, state, "integrations.microsoft.login.callback"
    )


@login_router.get("/callback", name="integrations.microsoft.login.callback")
async def login_callback(
    request: Request,
    auth_subject: WebUserOrAnonymous,
    session: AsyncSession = Depends(get_db_session),
    access_token_state: tuple[OAuth2Token, str | None] = Depends(
        oauth2_login_authorize_callback
    ),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    token_data, raw_state = access_token_state
    state_data = await validate_callback(
        request, redis, token_data, raw_state, type="microsoft"
    )

    return_to = state_data.get("return_to", None)

    if is_user_principal(auth_subject):
        return RedirectResponse(get_safe_return_url(return_to), 303)

    attribution_data = state_data.get("signup_attribution")
    signup_attr = (
        UserSignupAttribution.model_validate(attribution_data)
        if attribution_data
        else None
    )

    try:
        user, is_signup = await microsoft_service.get_updated_or_create(
            session,
            token=token_data,
            signup_attribution=signup_attr,
        )
    except MicrosoftServiceError as exc:
        raise OAuthCallbackError(
            exc.message, exc.status_code, return_to=return_to
        ) from exc

    if is_signup:
        posthog.user_signup(user, "microsoft")
    else:
        posthog.user_login(user, "microsoft")

    response = await auth_service.get_login_response(
        session, request, user, return_to=return_to
    )
    clear_login_cookie(request, response)
    return response


# ---------------------------------------------------------------------------
# Link sub-router
# ---------------------------------------------------------------------------

link_router = APIRouter(
    prefix="/link",
    tags=["integrations_microsoft_link", APITag.private],
)


@link_router.get("/authorize", name="integrations.microsoft.link.authorize")
async def link_authorize(
    request: Request,
    auth_subject: WebUserWrite,
    return_to: ReturnTo,
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    state: dict[str, Any] = {
        "return_to": return_to,
        "user_id": str(auth_subject.subject.id),
    }

    return await create_microsoft_authorization_response(
        request, redis, state, "integrations.microsoft.link.callback"
    )


@link_router.get("/callback", name="integrations.microsoft.link.callback")
async def link_callback(
    request: Request,
    auth_subject: WebUserWrite,
    session: AsyncSession = Depends(get_db_session),
    access_token_state: tuple[OAuth2Token, str | None] = Depends(
        oauth2_link_authorize_callback
    ),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    token_data, raw_state = access_token_state
    state_data = await validate_callback(
        request, redis, token_data, raw_state, type="microsoft"
    )

    return_to = state_data.get("return_to", None)
    state_user_id = state_data.get("user_id")

    if state_user_id is None or auth_subject.subject.id != uuid.UUID(state_user_id):
        raise OAuthCallbackError("Invalid user for linking", return_to=return_to)

    try:
        await microsoft_service.link_user(
            session, user=auth_subject.subject, token=token_data
        )
    except MicrosoftServiceError as exc:
        raise OAuthCallbackError(
            exc.message, exc.status_code, return_to=return_to
        ) from exc

    response = RedirectResponse(get_safe_return_url(return_to), 303)
    clear_login_cookie(request, response)
    return response


# ---------------------------------------------------------------------------
# Top-level router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/integrations/microsoft",
    tags=["integrations_microsoft", APITag.private],
)
router.include_router(login_router)
router.include_router(link_router)
