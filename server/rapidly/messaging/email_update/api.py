"""Email-update HTTP routes: request change and verify token.

Exposes endpoints for initiating an email-address change (sends
verification link) and confirming the change via the signed token.
"""

from fastapi import Depends, Form
from fastapi.responses import RedirectResponse

from rapidly.config import settings
from rapidly.core.db.postgres import AsyncSession
from rapidly.core.http import ReturnTo, get_safe_return_url
from rapidly.errors import RedirectionError
from rapidly.identity.auth.dependencies import WebUserWrite
from rapidly.openapi import APITag
from rapidly.postgres import get_db_session
from rapidly.routing import APIRouter

from .actions import EmailUpdateError
from .actions import email_update as email_update_service
from .types import EmailUpdateRequest

router = APIRouter(prefix="/email-update", tags=["email-update", APITag.private])


@router.post("/request", status_code=202)
async def request_email_update(
    email_update_request: EmailUpdateRequest,
    auth_subject: WebUserWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    email_update_record, token = await email_update_service.request_email_update(
        email_update_request.email,
        session,
        auth_subject,
    )

    await email_update_service.send_email(
        email_update_record,
        token,
        base_url=str(settings.generate_frontend_url("/verify-email")),
        extra_url_params=(
            {"return_to": email_update_request.return_to}
            if email_update_request.return_to
            else {}
        ),
    )


@router.post("/verify")
async def verify_email_update(
    return_to: ReturnTo,
    auth_subject: WebUserWrite,
    token: str = Form(),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        await email_update_service.verify(session, token)
    except EmailUpdateError as e:
        raise RedirectionError(e.message, e.status_code, return_to=return_to) from e

    return_url = get_safe_return_url(return_to)
    response = RedirectResponse(return_url, 303)

    return response
