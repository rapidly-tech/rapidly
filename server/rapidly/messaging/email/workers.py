"""Background task definitions for email processing."""

import hashlib

import structlog

from rapidly.worker import RedisMiddleware, TaskPriority, actor

from .sender import Attachment, email_sender

_log = structlog.get_logger(__name__)

_EMAIL_DEDUP_TTL_SECONDS: int = 60 * 60  # 1 hour


def _email_dedup_key(to_email_addr: str, subject: str, html_content: str) -> str:
    """Build a Redis key for deduplicating email sends."""
    digest = hashlib.sha256(
        f"{to_email_addr}:{subject}:{html_content}".encode()
    ).hexdigest()[:16]
    return f"email:dedup:{digest}"


@actor(actor_name="email.send", priority=TaskPriority.HIGH)
async def email_send(
    to_email_addr: str,
    subject: str,
    html_content: str,
    from_name: str,
    email_headers: dict[str, str] | None,
    reply_to_name: str | None,
    reply_to_email_addr: str | None,
    attachments: list[Attachment] | None = None,
) -> None:
    # Deduplication: skip if this exact email was already sent recently
    r = RedisMiddleware.get()
    dedup_key = _email_dedup_key(to_email_addr, subject, html_content)
    if await r.exists(dedup_key):
        _log.info(
            "email.send.deduplicated",
            to=to_email_addr,
            subject=subject,
        )
        return

    await email_sender.send(
        to_email_addr=to_email_addr,
        subject=subject,
        html_content=html_content,
        from_name=from_name,
        email_headers=email_headers,
        reply_to_name=reply_to_name,
        reply_to_email_addr=reply_to_email_addr,
        attachments=attachments,
    )

    # Mark as sent only after successful delivery
    await r.set(dedup_key, "1", ex=_EMAIL_DEDUP_TTL_SECONDS)
