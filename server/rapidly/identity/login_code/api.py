"""Login-code (magic link) HTTP routes: request and verify.

Exposes endpoints for requesting a one-time login code sent via
email and verifying the code to establish a user session.
"""

from urllib.parse import urlencode

import structlog
from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse

from rapidly.config import settings
from rapidly.core.db.postgres import AsyncSession
from rapidly.core.email import EmailStrDNS
from rapidly.core.http import ReturnTo
from rapidly.core.rate_limit import check_otp_rate_limit
from rapidly.identity.auth import actions as auth_service
from rapidly.identity.auth.dependencies import WebUserOrAnonymous
from rapidly.identity.auth.models import is_user_principal
from rapidly.openapi import APITag
from rapidly.postgres import get_db_session
from rapidly.posthog import posthog
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from . import actions as login_code_service
from .actions import LoginCodeError
from .types import LoginCodeRequest

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/login-code", tags=["login_code", APITag.private])


@router.post("/request", status_code=202)
async def request_login_code(
    login_code_request: LoginCodeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Request a login code.
    """
    code_model, code = await login_code_service.request(
        session,
        login_code_request.email,
        return_to=login_code_request.return_to,
        signup_attribution=login_code_request.attribution,
    )

    # Send the code email
    await login_code_service.send(code_model, code)


@router.post("/authenticate")
async def authenticate_login_code(
    request: Request,
    return_to: ReturnTo,
    email: EmailStrDNS,
    auth_subject: WebUserOrAnonymous,
    code: str = Form(),
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """
    Authenticate with a login code.
    """
    if is_user_principal(auth_subject):
        return RedirectResponse(return_to, 303)

    await check_otp_rate_limit(redis, request, key_prefix="login")

    try:
        user, is_signup = await login_code_service.authenticate(
            session, code=code, email=email
        )
    except LoginCodeError as e:
        base_url = str(settings.generate_frontend_url("/login/code/verify"))
        url_params = {
            "return_to": return_to,
            "email": request.query_params.get("email"),
            "error": e.message,
        }
        failed_login_return_to = f"{base_url}?{urlencode(url_params)}"
        return RedirectResponse(failed_login_return_to, 303)

    # Event tracking last to ensure business critical data is stored first
    if is_signup:
        posthog.user_signup(user, "code")
    else:
        posthog.user_login(user, "code")

    return await auth_service.get_login_response(
        session, request, user, return_to=return_to
    )
