"""Email-address change verification service.

Generates a time-limited verification token when a user requests an
email change, delivers the confirmation link, and applies the update
once the token is validated.  Expired records are cleaned up by a
periodic background task.
"""

from math import ceil
from urllib.parse import urlencode

from rapidly.config import settings
from rapidly.core.crypto import generate_token_hash_pair, get_token_hash
from rapidly.core.utils import now_utc
from rapidly.errors import RapidlyError, RequestValidationError, validation_error
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.messaging.email.react import render_email_template
from rapidly.messaging.email.sender import enqueue_email
from rapidly.messaging.email.types import EmailUpdateEmail, EmailUpdateProps
from rapidly.models import EmailVerification
from rapidly.models.user import User
from rapidly.platform.user.queries import UserRepository
from rapidly.postgres import AsyncSession

from .queries import EmailVerificationRepository

TOKEN_PREFIX = "rapidly_ev_"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EmailUpdateError(RapidlyError): ...


class InvalidEmailUpdate(EmailUpdateError):
    def __init__(self) -> None:
        super().__init__(
            "This email update request is invalid or has expired.", status_code=401
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EmailUpdateService:
    """Verification-token flow for changing a user's email address."""

    # ------------------------------------------------------------------
    # Token verification
    # ------------------------------------------------------------------

    async def verify(self, session: AsyncSession, token: str) -> User:
        hashed = get_token_hash(token, secret=settings.SECRET)
        repo = EmailVerificationRepository.from_session(session)
        record = await repo.get_by_token_hash(hashed)

        if record is None:
            raise InvalidEmailUpdate()

        target_user = record.user
        user_repo = UserRepository.from_session(session)
        target_user = await user_repo.update(
            target_user, update_dict={"email": record.email}
        )

        await repo.delete(record)

        return target_user

    # ------------------------------------------------------------------
    # Request creation
    # ------------------------------------------------------------------

    async def request_email_update(
        self,
        email: str,
        session: AsyncSession,
        auth_subject: AuthPrincipal[User],
    ) -> tuple[EmailVerification, str]:
        current_user = auth_subject.subject

        user_repo = UserRepository.from_session(session)
        collision = await user_repo.get_by_email(email)
        if collision is not None and collision.id != current_user.id:
            raise RequestValidationError(
                [
                    validation_error(
                        "email", "Another user is already using this email.", email
                    )
                ]
            )

        raw_token, hashed_token = generate_token_hash_pair(
            secret=settings.SECRET, prefix=TOKEN_PREFIX
        )
        repo = EmailVerificationRepository.from_session(session)
        verification = EmailVerification(
            email=email, token_hash=hashed_token, user=current_user
        )
        await repo.create(verification, flush=True)

        return verification, raw_token

    # ------------------------------------------------------------------
    # Email delivery
    # ------------------------------------------------------------------

    async def send_email(
        self,
        email_update_record: EmailVerification,
        token: str,
        base_url: str,
        *,
        extra_url_params: dict[str, str] | None = None,
    ) -> None:
        remaining = email_update_record.expires_at - now_utc()
        lifetime_minutes = int(ceil(remaining.total_seconds() / 60))

        target_email = email_update_record.email
        params = {"token": token, **(extra_url_params or {})}
        rendered_body = render_email_template(
            EmailUpdateEmail(
                props=EmailUpdateProps(
                    email=target_email,
                    token_lifetime_minutes=lifetime_minutes,
                    url=f"{base_url}?{urlencode(params)}",
                )
            )
        )

        enqueue_email(
            to_email_addr=target_email,
            subject="Update your email",
            html_content=rendered_body,
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def delete_expired_record(self, session: AsyncSession) -> None:
        repo = EmailVerificationRepository.from_session(session)
        await repo.delete_expired()


email_update = EmailUpdateService()
