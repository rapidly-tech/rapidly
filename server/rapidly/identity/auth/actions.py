"""User session authentication: creation, validation, cookie management."""

from datetime import datetime, timedelta

import structlog
from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from rapidly.config import settings
from rapidly.core.crypto import generate_token_hash_pair
from rapidly.core.http import get_safe_return_url
from rapidly.core.utils import now_utc
from rapidly.enums import TokenType
from rapidly.identity.auth.queries import UserSessionRepository
from rapidly.identity.auth.scope import Scope
from rapidly.logging import Logger
from rapidly.models import User, UserSession
from rapidly.postgres import AsyncSession

_log: Logger = structlog.get_logger(__name__)

USER_SESSION_TOKEN_PREFIX = "rapidly_us_"
_DEFAULT_LOGIN_SCOPES: list[Scope] = [Scope.web_read, Scope.web_write]


# ── Session management ──


async def get_login_response(
    session: AsyncSession,
    request: Request,
    user: User,
    *,
    return_to: str | None = None,
) -> RedirectResponse:
    token, user_session = await _create_user_session(
        session=session,
        user=user,
        user_agent=request.headers.get("User-Agent", ""),
        scopes=_DEFAULT_LOGIN_SCOPES,
    )

    return_url = get_safe_return_url(return_to)
    response = RedirectResponse(return_url, 303)
    _set_session_cookie(request, response, token, user_session.expires_at)
    return response


async def get_logout_response(
    session: AsyncSession, request: Request, user_session: UserSession | None
) -> RedirectResponse:
    if user_session is not None:
        repo = UserSessionRepository.from_session(session)
        await repo.delete(user_session)
    response = RedirectResponse(settings.FRONTEND_BASE_URL)
    _set_session_cookie(request, response, "", 0)
    return response


# ── Token validation ──


async def authenticate(
    session: AsyncSession,
    request: Request,
    cookie: str = settings.USER_SESSION_COOKIE_KEY,
) -> UserSession | None:
    token = request.cookies.get(cookie)
    if not token or not token.isascii():
        return None

    repo = UserSessionRepository.from_session(session)
    user_session = await repo.get_by_token(token)
    if user_session is None or not user_session.user.can_authenticate:
        return None

    return user_session


async def delete_expired(session: AsyncSession) -> None:
    repo = UserSessionRepository.from_session(session)
    await repo.delete_expired()


async def revoke_leaked(
    session: AsyncSession,
    token: str,
    token_type: TokenType,
    *,
    notifier: str,
    url: str | None,
) -> bool:
    repo = UserSessionRepository.from_session(session)
    user_session = await repo.get_by_token(token, include_expired=True)
    if user_session is None:
        return False

    await repo.delete(user_session)
    _log.info(
        "Revoked leaked session token",
        session_id=user_session.id,
        notifier=notifier,
        url=url,
    )
    return True


# ── Internal helpers ──


async def _create_user_session(
    session: AsyncSession,
    user: User,
    *,
    user_agent: str,
    scopes: list[Scope],
    expire_in: timedelta = settings.USER_SESSION_TTL,
    is_impersonation: bool = False,
) -> tuple[str, UserSession]:
    token, token_hash = generate_token_hash_pair(
        secret=settings.SECRET, prefix=USER_SESSION_TOKEN_PREFIX
    )
    user_session = UserSession(
        token=token_hash,
        user_agent=user_agent,
        user=user,
        scopes=scopes,
        expires_at=now_utc() + expire_in,
        is_impersonation=is_impersonation,
    )
    repo = UserSessionRepository.from_session(session)
    await repo.create(user_session, flush=True)

    # Evict oldest sessions if the user exceeds the per-user limit
    max_sessions = settings.USER_SESSION_MAX_PER_USER
    active_count = await repo.count_active_for_user(user.id)
    if active_count > max_sessions:
        await repo.evict_oldest_for_user(user.id, keep=max_sessions)

    return token, user_session


def _set_session_cookie[R: Response](
    request: Request, response: R, value: str, expires: int | datetime
) -> None:
    cookie_kwargs: dict[str, object] = {
        "key": settings.USER_SESSION_COOKIE_KEY,
        "value": value,
        "expires": expires,
        "path": "/",
        "secure": not settings.is_development(),
        "httponly": True,
        "samesite": "lax",
    }
    if settings.USER_SESSION_COOKIE_DOMAIN:
        cookie_kwargs["domain"] = settings.USER_SESSION_COOKIE_DOMAIN
    response.set_cookie(**cookie_kwargs)  # type: ignore[arg-type]
