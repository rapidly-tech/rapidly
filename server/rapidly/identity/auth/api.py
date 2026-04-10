"""Authentication routes: logout and session management."""

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse

from rapidly.openapi import APITag
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

from . import actions as auth_service

router = APIRouter(tags=["auth", APITag.private])


@router.get("/auth/logout", summary="End session")
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    """Invalidate the current session and redirect to the frontend."""
    user_session = await auth_service.authenticate(session, request)
    return await auth_service.get_logout_response(session, request, user_session)
