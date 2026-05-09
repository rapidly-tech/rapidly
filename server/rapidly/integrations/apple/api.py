"""Apple Sign-In OAuth routes: authorization and POST-based callback.

Manages the Apple OAuth2 redirect flow including state-cookie management,
the ``form_post`` response mode callback, and account linking with
existing Rapidly users.
"""

import secrets
from typing import Any

from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse
from httpx_oauth.integrations.fastapi import (
    OAuth2AuthorizeCallbackError,
)
from httpx_oauth.oauth2 import GetAccessTokenError

from rapidly.core.geolocation import get_request_geo
from rapidly.core.http import ReturnTo
from rapidly.core.oauth import (
    OAuthCallbackError,
    clear_login_cookie,
    set_login_cookie,
    store_oauth_state,
    validate_callback,
)
from rapidly.errors import NotPermitted
from rapidly.identity.auth import actions as auth_service
from rapidly.identity.auth.dependencies import WebUserOrAnonymous
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

from . import actions as apple_service
from .actions import AppleServiceError, get_apple_oauth_client

router = APIRouter(
    prefix="/integrations/apple",
    tags=["integrations_apple", APITag.private],
)


# ---------------------------------------------------------------------------
# Callback (POST-based -- Apple sends form_post)
# ---------------------------------------------------------------------------


@router.post("/callback", name="integrations.apple.callback")
async def apple_callback(
    request: Request,
    auth_subject: WebUserOrAnonymous,
    code: str | None = Form(None),
    code_verifier: str | None = Form(None),
    state: str | None = Form(None),
    error: str | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    if is_user_principal(auth_subject):
        raise NotPermitted()

    if code is None or error is not None:
        raise OAuth2AuthorizeCallbackError(
            status_code=400,
            detail=error if error is not None else None,
        )

    callback_uri = str(request.url_for("integrations.apple.callback"))
    try:
        apple_client = get_apple_oauth_client(secret=True)
        token_data = await apple_client.get_access_token(
            code, callback_uri, code_verifier
        )
    except GetAccessTokenError as exc:
        raise OAuth2AuthorizeCallbackError(
            status_code=500,
            detail=exc.message,
            response=exc.response,
        ) from exc

    state_data = await validate_callback(
        request, redis, token_data, state, type="apple", cross_site=True
    )

    return_to = state_data.get("return_to", None)

    attribution_data = state_data.get("signup_attribution")
    signup_attr = (
        UserSignupAttribution.model_validate(attribution_data)
        if attribution_data
        else None
    )

    try:
        user, is_signup = await apple_service.get_updated_or_create(
            session,
            token=token_data,
            signup_attribution=signup_attr,
        )
    except AppleServiceError as exc:
        raise OAuthCallbackError(
            exc.message, exc.status_code, return_to=return_to
        ) from exc

    geo = get_request_geo(request)
    if is_signup:
        posthog.user_signup(user, "apple", geo=geo)
    else:
        posthog.user_login(user, "apple", geo=geo)

    response = await auth_service.get_login_response(
        session, request, user, return_to=return_to
    )
    clear_login_cookie(request, response, cross_site=True)
    return response


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


@router.get("/authorize", name="integrations.apple.authorize")
async def apple_authorize(
    request: Request,
    auth_subject: WebUserOrAnonymous,
    return_to: ReturnTo,
    signup_attribution: UserSignupAttributionQuery,
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    if is_user_principal(auth_subject):
        raise NotPermitted()

    state: dict[str, Any] = {"return_to": return_to}
    if signup_attribution:
        state["signup_attribution"] = signup_attribution.model_dump(exclude_unset=True)

    nonce = secrets.token_urlsafe()
    state_with_nonce = {**state, "nonce": nonce}
    await store_oauth_state(redis, nonce, state_with_nonce, type="apple")

    callback_uri = str(request.url_for("integrations.apple.callback"))
    apple_client = get_apple_oauth_client()
    auth_url = await apple_client.get_authorization_url(
        redirect_uri=callback_uri,
        state=nonce,
        extras_params={"response_mode": "form_post"},
    )
    response = RedirectResponse(auth_url, 303)
    set_login_cookie(request, response, nonce, cross_site=True)
    return response
