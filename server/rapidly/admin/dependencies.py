"""FastAPI dependency overrides for admin panel authentication and authorization.

The ``get_admin`` dependency checks for both the regular user session and
an impersonation session (used when an admin is acting-as another user).
The original admin session always takes priority to prevent privilege
escalation.
"""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.exceptions import HTTPException

from rapidly.config import settings
from rapidly.identity.auth import actions as auth_service
from rapidly.models.user_session import UserSession
from rapidly.postgres import AsyncSession, get_db_session


async def get_admin(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> UserSession:
    """Resolve the current admin user session or raise 401/403.

    When an impersonation cookie is present, its session is treated as
    the authoritative identity so that the real admin's privileges are
    honoured even while impersonating a non-admin user.
    """
    user_session = await auth_service.authenticate(session, request)

    # If an impersonation cookie exists, that identity takes precedence.
    orig_user_session = await auth_service.authenticate(
        session, request, cookie=settings.IMPERSONATION_COOKIE_KEY
    )
    if orig_user_session is not None:
        user_session = orig_user_session

    if user_session is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not user_session.user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    return user_session
