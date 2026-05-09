"""One-time login code generation, delivery, and verification."""

import datetime
import secrets
import string
from math import ceil

import structlog

from rapidly.config import Environment, settings
from rapidly.core.crypto import get_token_hash
from rapidly.core.utils import now_utc
from rapidly.errors import RapidlyError
from rapidly.logging import Logger
from rapidly.messaging.email.react import render_email_template
from rapidly.messaging.email.sender import enqueue_email
from rapidly.messaging.email.types import LoginCodeEmail, LoginCodeProps
from rapidly.models import LoginCode, User
from rapidly.platform.user import actions as user_service
from rapidly.platform.user.queries import UserRepository
from rapidly.platform.user.types import UserSignupAttribution
from rapidly.postgres import AsyncSession

from .queries import LoginCodeRepository

_log: Logger = structlog.get_logger(__name__)

# Character pool for OTP codes (uppercase alphanumeric).
_CODE_ALPHABET: str = string.ascii_uppercase + string.digits


class LoginCodeError(RapidlyError):
    """Base for login-code business logic errors."""


class LoginCodeInvalidOrExpired(LoginCodeError):
    def __init__(self) -> None:
        super().__init__("This login code is invalid or has expired.", status_code=401)


# ── Issue & deliver ──


async def request(
    session: AsyncSession,
    email: str,
    *,
    return_to: str | None = None,
    signup_attribution: UserSignupAttribution | None = None,
) -> tuple[LoginCode, str]:
    user_repo = UserRepository.from_session(session)
    existing_user = await user_repo.get_by_email(email)

    code, code_hash = _generate_code_hash()
    ttl = datetime.timedelta(seconds=settings.LOGIN_CODE_TTL_SECONDS)

    record = LoginCode(
        code_hash=code_hash,
        email=email,
        user_id=existing_user.id if existing_user is not None else None,
        expires_at=now_utc() + ttl,
    )
    repo = LoginCodeRepository.from_session(session)
    await repo.create(record, flush=True)
    return record, code


async def send(login_code: LoginCode, code: str) -> None:
    remaining = login_code.expires_at - now_utc()
    lifetime_minutes = int(ceil(remaining.total_seconds() / 60))

    html = render_email_template(
        LoginCodeEmail(
            props=LoginCodeProps(
                email=login_code.email,
                code=code,
                code_lifetime_minutes=lifetime_minutes,
            )
        )
    )
    enqueue_email(
        to_email_addr=login_code.email,
        subject="Sign in to Rapidly",
        html_content=html,
    )

    if settings.is_development():
        _log.debug("Login code for %s: %s***", login_code.email, code[:2])


# ── Verification ──


async def authenticate(
    session: AsyncSession,
    code: str,
    email: str,
    *,
    signup_attribution: UserSignupAttribution | None = None,
) -> tuple[User, bool]:
    # Fast-path for App Store review accounts.
    if bypass := await _try_app_review_bypass(session, code, email, signup_attribution):
        return bypass

    login_code = await _lookup_valid_code(session, code, email)
    if login_code is None:
        raise LoginCodeInvalidOrExpired()

    user, is_signup = await _resolve_user(session, login_code, signup_attribution)
    repo = LoginCodeRepository.from_session(session)
    await repo.delete(login_code)
    return user, is_signup


async def _lookup_valid_code(
    session: AsyncSession, code: str, email: str
) -> LoginCode | None:
    code_hash = get_token_hash(code, secret=settings.SECRET)
    repo = LoginCodeRepository.from_session(session)
    return await repo.get_valid_by_hash_and_email(code_hash, email)


async def _resolve_user(
    session: AsyncSession,
    login_code: LoginCode,
    signup_attribution: UserSignupAttribution | None,
) -> tuple[User, bool]:
    """Get or create the user for a validated code, marking email verified."""
    is_signup = False
    user = login_code.user
    if user is None:
        user, is_signup = await user_service.get_by_email_or_create(
            session, login_code.email, signup_attribution=signup_attribution
        )

    if not user.email_verified:
        is_signup = True
        user.email_verified = True
        user_repo = UserRepository.from_session(session)
        await user_repo.update(user)

    return user, is_signup


# ── Internals ──


async def _try_app_review_bypass(
    session: AsyncSession,
    code: str,
    email: str,
    signup_attribution: UserSignupAttribution | None,
) -> tuple[User, bool] | None:
    """Allow a fixed test account for App Store / Play Store review."""
    if settings.ENV not in (Environment.development, Environment.testing):
        return None
    if not (settings.APP_REVIEW_EMAIL and settings.APP_REVIEW_OTP_CODE):
        return None
    if email.lower() != settings.APP_REVIEW_EMAIL.lower():
        return None
    if not secrets.compare_digest(code, settings.APP_REVIEW_OTP_CODE):
        return None
    return await user_service.get_by_email_or_create(
        session, email, signup_attribution=signup_attribution
    )


# ── Code generation ──


def _generate_code_hash() -> tuple[str, str]:
    code = "".join(
        secrets.choice(_CODE_ALPHABET) for _ in range(settings.LOGIN_CODE_LENGTH)
    )
    return code, get_token_hash(code, secret=settings.SECRET)
