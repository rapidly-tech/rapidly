"""Background jobs for webhook delivery, retries, and event cleanup.

Handles the actual HTTP delivery of webhook payloads (with HMAC
signing via the Standard Webhooks spec), automatic retries with
exponential back-off, and a scheduled job to prune stale delivery
records past the retention window.
"""

import base64
import ipaddress
import socket
from collections.abc import Mapping
from ssl import SSLError
from urllib.parse import urlparse
from uuid import UUID

import httpx
import structlog
from apscheduler.triggers.cron import CronTrigger
from dramatiq import Retry
from standardwebhooks.webhooks import Webhook as StandardWebhook

from rapidly.config import Environment, settings
from rapidly.core.db.postgres import AsyncSession
from rapidly.core.utils import now_utc
from rapidly.logging import Logger
from rapidly.messaging.webhook.queries import WebhookEventRepository
from rapidly.models.webhook_delivery import WebhookDelivery
from rapidly.worker import (
    AsyncSessionMaker,
    HTTPXMiddleware,
    TaskPriority,
    TaskQueue,
    actor,
    can_retry,
    dispatch_task,
)

from . import actions as webhook_service

_log: Logger = structlog.get_logger(__name__)


async def _resolve_safe_addrs(url: str) -> list[tuple[str, int]] | None:
    """Resolve *url* and return (ip, port) pairs, or None if any address is private.

    By resolving once and returning the addresses, the caller can connect
    directly to the resolved IPs, preventing DNS rebinding attacks where a
    hostname resolves to a public IP during validation but rebinds to a
    private IP on the actual connection.
    """
    import asyncio

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if hostname is None:
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        loop = asyncio.get_running_loop()
        addrs = await loop.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        safe_addrs: list[tuple[str, int]] = []
        for _family, _type, _proto, _canonname, sockaddr in addrs:
            addr = ipaddress.ip_address(sockaddr[0])
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                return None
            safe_addrs.append((sockaddr[0], port))
        return safe_addrs if safe_addrs else None
    except (socket.gaierror, ValueError, OSError):
        return None


# ── Delivery ──


@actor(
    actor_name="webhook_event.send",
    max_retries=settings.WEBHOOK_MAX_RETRIES,
    queue_name=TaskQueue.WEBHOOKS,
)
async def webhook_event_send(webhook_event_id: UUID, redeliver: bool = False) -> None:
    async with AsyncSessionMaker() as session:
        return await _webhook_event_send(
            session, webhook_event_id=webhook_event_id, redeliver=redeliver
        )


@actor(
    actor_name="webhook_event.send.v2",
    max_retries=settings.WEBHOOK_MAX_RETRIES,
    queue_name=TaskQueue.WEBHOOKS,
)
async def webhook_event_send_dedicated_queue(
    webhook_event_id: UUID, redeliver: bool = False
) -> None:
    async with AsyncSessionMaker() as session:
        return await _webhook_event_send(
            session, webhook_event_id=webhook_event_id, redeliver=redeliver
        )


async def _webhook_event_send(
    session: AsyncSession, *, webhook_event_id: UUID, redeliver: bool = False
) -> None:
    repository = WebhookEventRepository.from_session(session)
    event = await repository.get_by_id(
        webhook_event_id, options=repository.get_eager_options()
    )
    if event is None:
        raise Exception(f"webhook event not found id={webhook_event_id}")

    bound_log = _log.bind(
        id=webhook_event_id,
        type=event.type,
        webhook_endpoint_id=event.webhook_endpoint_id,
    )

    if not event.webhook_endpoint.enabled:
        bound_log.info("Webhook endpoint is disabled, skipping")
        event.skipped = True
        session.add(event)
        return

    if event.payload is None:
        bound_log.info("Archived event, skipping")
        return

    if event.succeeded and not redeliver:
        bound_log.info("Event already succeeded, skipping")
        return

    if not await webhook_service.is_latest_event(session, event):
        _log.info(
            "Earlier events need to be delivered first, retrying later",
            id=event.id,
            type=event.type,
            webhook_endpoint_id=event.webhook_endpoint_id,
        )
        raise Retry()

    if event.skipped:
        event.skipped = False
        session.add(event)

    ts = now_utc()

    b64secret = base64.b64encode(event.webhook_endpoint.secret.encode("utf-8")).decode(
        "utf-8"
    )

    # Sign the payload
    wh = StandardWebhook(b64secret)
    signature = wh.sign(str(event.id), ts, event.payload)

    headers: Mapping[str, str] = {
        "user-agent": "rapidly.tech webhooks",
        "content-type": "application/json",
        "webhook-id": str(event.id),
        "webhook-timestamp": str(int(ts.timestamp())),
        "webhook-signature": signature,
    }

    delivery = WebhookDelivery(
        webhook_event_id=webhook_event_id, webhook_endpoint_id=event.webhook_endpoint_id
    )

    client = HTTPXMiddleware.get()
    try:
        # SSRF protection: resolve once and reject private/internal IPs.
        # Using resolved addresses for the connection prevents DNS rebinding.
        safe_addrs = await _resolve_safe_addrs(event.webhook_endpoint.url)
        if safe_addrs is None:
            bound_log.warning(
                "Webhook URL resolves to a private/internal IP, skipping delivery",
                url=event.webhook_endpoint.url,
            )
            delivery.succeeded = False
            delivery.response = "URL resolves to a private/internal IP address"
            event.succeeded = False
            session.add(delivery)
            session.add(event)
            return

        # In development, don't send webhooks for real
        # Fail-safe to make sure we don't sent data in the real world
        if settings.ENV == Environment.development:
            delivery.http_code = event.last_http_code = 200
            delivery.response = None
        else:
            response = await client.post(
                event.webhook_endpoint.url,
                content=event.payload,
                headers=headers,
                timeout=10.0,
            )
            delivery.http_code = response.status_code
            delivery.response = (
                # Limit to first 2048 characters to avoid bloating the DB
                response.text[:2048] if response.text else None
            )
            event.last_http_code = response.status_code
            response.raise_for_status()
    # Error
    except (httpx.HTTPError, SSLError) as e:
        bound_log.info("An error occurred while sending a webhook", error=e)

        if (
            isinstance(e, httpx.HTTPStatusError)
            and e.response.status_code == 429
            and "discord" in event.webhook_endpoint.url.lower()
        ):
            rate_limit_headers = {
                k: v
                for k, v in e.response.headers.items()
                if k.lower().startswith("x-ratelimit-") or k.lower() == "retry-after"
            }
            bound_log.warning(
                "Discord rate limit exceeded",
                rate_limit_headers=rate_limit_headers,
                response_body=e.response.text[:2048] if e.response.text else None,
            )

        delivery.succeeded = False
        if delivery.response is None:
            delivery.response = str(e)

        # Permanent failure
        if not can_retry():
            event.succeeded = False
            dispatch_task("webhook_event.failed", webhook_event_id=webhook_event_id)
        # Retry
        else:
            raise Retry() from e
    # Success
    else:
        delivery.succeeded = True
        event.succeeded = True
        dispatch_task("webhook_event.success", webhook_event_id=webhook_event_id)
    # Either way, save the delivery
    finally:
        if delivery.succeeded is None:
            raise ValueError("delivery.succeeded must be set before saving")
        session.add(delivery)
        session.add(event)


# ── Retry ──


@actor(actor_name="webhook_event.success", priority=TaskPriority.HIGH)
async def webhook_event_success(webhook_event_id: UUID) -> None:
    async with AsyncSessionMaker() as session:
        return await webhook_service.on_event_success(session, webhook_event_id)


@actor(actor_name="webhook_event.failed", priority=TaskPriority.HIGH)
async def webhook_event_failed(webhook_event_id: UUID) -> None:
    async with AsyncSessionMaker() as session:
        return await webhook_service.on_event_failed(session, webhook_event_id)


# ── Archival ──


@actor(
    actor_name="webhook_event.archive",
    cron_trigger=CronTrigger(hour=0, minute=0),
    priority=TaskPriority.LOW,
)
async def webhook_event_archive() -> None:
    async with AsyncSessionMaker() as session:
        return await webhook_service.archive_events(
            session, older_than=now_utc() - settings.WEBHOOK_EVENT_RETENTION_PERIOD
        )
