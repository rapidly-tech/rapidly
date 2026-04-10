"""Stripe webhook ingestion endpoints (direct and Connect)."""

import stripe
import structlog
from fastapi import Depends, HTTPException, Query, Request
from starlette.responses import RedirectResponse

from rapidly.analytics.external_event import actions as external_event_service
from rapidly.config import settings
from rapidly.core.http import get_safe_return_url
from rapidly.models.external_event import ExternalEventSource
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

_log = structlog.get_logger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(
    prefix="/integrations/stripe", tags=["integrations_stripe"], include_in_schema=False
)

# ── Accepted webhook event types ──────────────────────────────────────

_DIRECT_WEBHOOKS: frozenset[str] = frozenset(
    {
        "identity.verification_session.verified",
        "identity.verification_session.processing",
        "identity.verification_session.requires_input",
        "identity.verification_session.canceled",
        # Destination Charges fire on the platform webhook
        "setup_intent.succeeded",
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "checkout.session.completed",
    }
)

_CONNECT_WEBHOOKS: frozenset[str] = frozenset(
    {
        "account.updated",
        "checkout.session.completed",
    }
)


async def _enqueue_stripe_event(session: AsyncSession, event: stripe.Event) -> None:
    """Persist and dispatch a Stripe webhook event for background processing."""
    event_type: str = event["type"]
    await external_event_service.enqueue(
        session,
        ExternalEventSource.stripe,
        f"stripe.webhook.{event_type}",
        event.id,
        event,
    )


# ── Routes ────────────────────────────────────────────────────────────


@router.get("/refresh", name="integrations.stripe.refresh")
async def stripe_connect_refresh(
    return_path: str | None = Query(None),
) -> RedirectResponse:
    if return_path is None:
        raise HTTPException(404)
    return RedirectResponse(get_safe_return_url(return_path))


class _WebhookEventGetter:
    """FastAPI dependency that verifies and parses a Stripe webhook payload."""

    __slots__ = ("_secret",)

    def __init__(self, secret: str) -> None:
        self._secret = secret

    async def __call__(self, request: Request) -> stripe.Event:
        body = await request.body()
        sig = request.headers["Stripe-Signature"]
        try:
            return stripe.Webhook.construct_event(body, sig, self._secret)
        except ValueError as exc:
            raise HTTPException(status_code=400) from exc
        except stripe.SignatureVerificationError as exc:
            raise HTTPException(status_code=401) from exc


@router.post("/webhook", status_code=202, name="integrations.stripe.webhook")
async def webhook(
    session: AsyncSession = Depends(get_db_session),
    event: stripe.Event = Depends(_WebhookEventGetter(settings.STRIPE_WEBHOOK_SECRET)),
) -> None:
    if event["type"] in _DIRECT_WEBHOOKS:
        await _enqueue_stripe_event(session, event)


@router.post(
    "/webhook-connect", status_code=202, name="integrations.stripe.webhook_connect"
)
async def webhook_connect(
    session: AsyncSession = Depends(get_db_session),
    event: stripe.Event = Depends(
        _WebhookEventGetter(settings.STRIPE_CONNECT_WEBHOOK_SECRET)
    ),
) -> None:
    if event["type"] in _CONNECT_WEBHOOKS:
        await _enqueue_stripe_event(session, event)
