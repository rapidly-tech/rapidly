"""Transactional email delivery via Gmail SMTP (production) or log sink (development)."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from email.message import EmailMessage
from typing import TypedDict

import aiosmtplib
import structlog
from email_validator import validate_email

from rapidly.config import EmailSender as EmailSenderType
from rapidly.config import settings
from rapidly.errors import RapidlyError
from rapidly.logging import Logger
from rapidly.worker import dispatch_task

_log: Logger = structlog.get_logger(__name__)

# ── Sender defaults ──────────────────────────────────────────────────

_FROM_NAME: str = settings.EMAIL_FROM_NAME
_REPLY_TO_NAME: str | None = settings.EMAIL_DEFAULT_REPLY_TO_NAME
_REPLY_TO_ADDRESS: str | None = settings.EMAIL_DEFAULT_REPLY_TO_EMAIL_ADDRESS

# Public aliases for external callers
DEFAULT_FROM_NAME = _FROM_NAME
DEFAULT_REPLY_TO_NAME = _REPLY_TO_NAME
DEFAULT_REPLY_TO_EMAIL_ADDRESS = _REPLY_TO_ADDRESS


def to_ascii_email(email: str) -> str:
    """Normalise *email* to ASCII, applying punycode to internationalised domains."""
    result = validate_email(email, check_deliverability=False)
    return result.ascii_email or email


class EmailSenderError(RapidlyError): ...


class SendEmailError(EmailSenderError):
    """Raised when the upstream email provider rejects a send request."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class Attachment(TypedDict):
    remote_url: str
    filename: str


class EmailSender(ABC):
    """Abstract base for email delivery backends."""

    @abstractmethod
    async def send(
        self,
        *,
        to_email_addr: str,
        subject: str,
        html_content: str,
        from_name: str = _FROM_NAME,
        email_headers: dict[str, str] | None = None,
        reply_to_name: str | None = _REPLY_TO_NAME,
        reply_to_email_addr: str | None = _REPLY_TO_ADDRESS,
        attachments: Iterable[Attachment] | None = None,
    ) -> None:
        pass


class LoggingEmailSender(EmailSender):
    """Dev-only sender that writes email metadata to the structured log."""

    async def send(
        self,
        *,
        to_email_addr: str,
        subject: str,
        html_content: str,
        from_name: str = _FROM_NAME,
        email_headers: dict[str, str] | None = None,
        reply_to_name: str | None = _REPLY_TO_NAME,
        reply_to_email_addr: str | None = _REPLY_TO_ADDRESS,
        attachments: Iterable[Attachment] | None = None,
    ) -> None:
        _log.info(
            "email.send.dev",
            to=to_ascii_email(to_email_addr),
            subject=subject,
            from_name=from_name,
        )


class GmailEmailSender(EmailSender):
    """Production sender that delivers email via Gmail SMTP with app passwords."""

    async def send(
        self,
        *,
        to_email_addr: str,
        subject: str,
        html_content: str,
        from_name: str = _FROM_NAME,
        email_headers: dict[str, str] | None = None,
        reply_to_name: str | None = _REPLY_TO_NAME,
        reply_to_email_addr: str | None = _REPLY_TO_ADDRESS,
        attachments: Iterable[Attachment] | None = None,
    ) -> None:
        ascii_to = to_ascii_email(to_email_addr)
        gmail_email = settings.GMAIL_EMAIL
        gmail_password = settings.GMAIL_APP_PASSWORD

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{gmail_email}>"
        msg["To"] = ascii_to
        if reply_to_name and reply_to_email_addr:
            msg["Reply-To"] = f"{reply_to_name} <{to_ascii_email(reply_to_email_addr)}>"
        for key, value in (email_headers or {}).items():
            msg[key] = value
        msg.set_content(subject)
        msg.add_alternative(html_content, subtype="html")

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.GMAIL_SMTP_HOST,
                port=settings.GMAIL_SMTP_PORT,
                start_tls=True,
                username=gmail_email,
                password=gmail_password,
            )
        except aiosmtplib.SMTPException as exc:
            _log.warning("email.gmail.failed", to=ascii_to, subject=subject, error=exc)
            raise SendEmailError(str(exc)) from exc

        _log.info("email.gmail.sent", to=ascii_to, subject=subject)


class EmailFromReply(TypedDict):
    from_name: str
    reply_to_name: str
    reply_to_email_addr: str


def enqueue_email(
    to_email_addr: str,
    subject: str,
    html_content: str,
    from_name: str = _FROM_NAME,
    email_headers: dict[str, str] | None = None,
    reply_to_name: str | None = _REPLY_TO_NAME,
    reply_to_email_addr: str | None = _REPLY_TO_ADDRESS,
    attachments: Iterable[Attachment] | None = None,
) -> None:
    """Push an email delivery job onto the background task queue."""
    dispatch_task(
        "email.send",
        to_email_addr=to_email_addr,
        subject=subject,
        html_content=html_content,
        from_name=from_name,
        email_headers=email_headers,
        reply_to_name=reply_to_name,
        reply_to_email_addr=reply_to_email_addr,
        attachments=attachments,
    )


# ── Module-level singleton ───────────────────────────────────────────


def _create_sender() -> EmailSender:
    if settings.EMAIL_SENDER == EmailSenderType.gmail:
        return GmailEmailSender()
    return LoggingEmailSender()


email_sender: EmailSender = _create_sender()
