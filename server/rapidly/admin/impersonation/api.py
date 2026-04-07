"""Admin panel user-impersonation routes.

Allows admin users to assume another user's session for debugging
purposes.  The original admin cookie is preserved so the session
can be restored afterwards.
"""

import uuid
from datetime import timedelta
from typing import Any

import structlog
from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import RedirectResponse

from rapidly.config import settings
from rapidly.identity.auth import actions as auth_service
from rapidly.identity.auth.dependencies import WebUserWrite
from rapidly.identity.auth.queries import UserSessionRepository
from rapidly.identity.auth.scope import Scope
from rapidly.models import (
    User,
    UserSession,
)
from rapidly.platform.user.queries import UserRepository
from rapidly.platform.workspace.queries import WorkspaceRepository
from rapidly.postgres import AsyncSession, get_db_session

from ..responses import HXRedirectResponse

_log = structlog.get_logger(__name__)

router = APIRouter()

# Cookie configuration shared by start / end handlers.
_COOKIE_DEFAULTS: dict[str, Any] = {
    "path": "/",
    "domain": settings.USER_SESSION_COOKIE_DOMAIN,
    "secure": not settings.is_development(),
    "samesite": "lax",
}

_IMPERSONATION_TTL = timedelta(minutes=60)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_session_cookie(
    response: Any, key: str, value: str, expires: Any, *, httponly: bool = True
) -> None:
    response.set_cookie(
        key, value=value, expires=expires, httponly=httponly, **_COOKIE_DEFAULTS
    )


def _clear_cookie(response: Any, key: str) -> None:
    response.delete_cookie(key, **_COOKIE_DEFAULTS)


async def _resolve_target_user(session: AsyncSession, user_id: str) -> User:
    repository = UserRepository.from_session(session)
    target = await repository.get_by_id(uuid.UUID(user_id))
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return target


# ---------------------------------------------------------------------------
# Start impersonation
# ---------------------------------------------------------------------------


@router.post("/start", name="admin:start_impersonation")
async def start_impersonation(
    request: Request,
    auth_subject: WebUserWrite,
    user_id: str = Form(),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Start impersonating a user. Only available to admin users."""

    if not auth_subject.subject.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can impersonate other users",
        )

    target_user = await _resolve_target_user(session, user_id)

    _log.warning(
        "Impersonation started",
        admin_user_id=str(auth_subject.subject.id),
        target_user_id=str(target_user.id),
    )

    # Create a read-only impersonation session for the target
    token, impersonation_session = await auth_service._create_user_session(
        session=session,
        user=target_user,
        user_agent=request.headers.get("User-Agent", ""),
        scopes=[Scope.web_read],
        expire_in=_IMPERSONATION_TTL,
        is_impersonation=True,
    )

    current_token = request.cookies.get(settings.USER_SESSION_COOKIE_KEY)

    # Redirect to the target's first workspace
    workspace_repo = WorkspaceRepository.from_session(session)
    user_workspaces = await workspace_repo.get_all_by_user(target_user.id)
    redirect_url = f"{settings.FRONTEND_BASE_URL}/dashboard/{user_workspaces[0].slug}"
    response = HXRedirectResponse(request, redirect_url, 307)

    # Preserve the admin session for later restoration
    if (
        current_token
        and auth_subject.session
        and isinstance(auth_subject.session, UserSession)
    ):
        _set_session_cookie(
            response,
            settings.IMPERSONATION_COOKIE_KEY,
            current_token,
            auth_subject.session.expires_at,
        )

    # Set the impersonated session
    _set_session_cookie(
        response,
        settings.USER_SESSION_COOKIE_KEY,
        token,
        impersonation_session.expires_at,
    )

    # Impersonation indicator — httpOnly for security; the frontend detects
    # impersonation via the server-side middleware header instead of reading
    # this cookie directly.
    _set_session_cookie(
        response,
        settings.IMPERSONATION_INDICATOR_COOKIE_KEY,
        "true",
        impersonation_session.expires_at,
    )

    return response


# ---------------------------------------------------------------------------
# End impersonation
# ---------------------------------------------------------------------------


@router.post("/end", name="admin:end_impersonation")
async def end_impersonation(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """End impersonation and restore the admin session."""

    admin_token = request.cookies.get(settings.IMPERSONATION_COOKIE_KEY)
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No admin session found"
        )

    # Clean up the impersonated session
    session_repo = UserSessionRepository.from_session(session)
    impersonated_user_id = None
    current_token = request.cookies.get(settings.USER_SESSION_COOKIE_KEY)
    if current_token:
        active_session = await session_repo.get_by_token(current_token)
        if active_session:
            impersonated_user_id = active_session.user_id
            await session_repo.delete(active_session)

    _log.warning(
        "Impersonation ended",
        admin_token_present=bool(admin_token),
        impersonated_user_id=str(impersonated_user_id)
        if impersonated_user_id
        else None,
    )

    # Verify the admin session is still usable and belongs to an admin
    admin_session = await session_repo.get_by_token(admin_token)
    if admin_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session expired or invalid",
        )

    if not admin_session.user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can end impersonation sessions",
        )

    # Build redirect back to the admin panel
    redirect_target = (
        settings.generate_admin_url(f"/users/{impersonated_user_id}")
        if impersonated_user_id
        else settings.generate_admin_url("/")
    )
    response = RedirectResponse(redirect_target)

    # Restore the admin cookie and clean up impersonation artifacts
    _set_session_cookie(
        response,
        settings.USER_SESSION_COOKIE_KEY,
        admin_token,
        admin_session.expires_at,
    )
    _clear_cookie(response, settings.IMPERSONATION_COOKIE_KEY)
    _clear_cookie(response, settings.IMPERSONATION_INDICATOR_COOKIE_KEY)

    return response
