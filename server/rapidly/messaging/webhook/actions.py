"""Webhook lifecycle: endpoint management, event creation, payload signing, and delivery."""

import datetime
from collections.abc import Sequence
from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from rapidly.config import settings
from rapidly.core.crypto import generate_token
from rapidly.core.db.postgres import AsyncReadSession, AsyncSession
from rapidly.core.pagination import PaginationParams
from rapidly.core.utils import now_utc
from rapidly.errors import RapidlyError, ResourceNotFound
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.identity.oauth2.constants import WEBHOOK_SECRET_PREFIX
from rapidly.logging import Logger
from rapidly.messaging.email.react import render_email_template
from rapidly.messaging.email.sender import enqueue_email
from rapidly.messaging.email.types import EmailAdapter
from rapidly.models import (
    User,
    WebhookDelivery,
    WebhookEvent,
    Workspace,
)
from rapidly.models.webhook_endpoint import (
    WebhookEndpoint,
    WebhookEventType,
)
from rapidly.platform.workspace.resolver import get_payload_workspace
from rapidly.platform.workspace_membership import (
    actions as workspace_membership_service,
)
from rapidly.worker import dispatch_task

from .queries import (
    WebhookDeliveryRepository,
    WebhookEndpointRepository,
    WebhookEventRepository,
)
from .types import WebhookEndpointCreate, WebhookEndpointUpdate
from .webhooks import SkipEvent, UnsupportedTarget, WebhookPayloadTypeAdapter

_log: Logger = structlog.get_logger(__name__)


class WebhookError(RapidlyError): ...


class EventDoesNotExist(WebhookError):
    def __init__(self, event_id: UUID) -> None:
        self.event_id = event_id
        message = f"Event with ID {event_id} does not exist."
        super().__init__(message)


class EventNotSuccessful(WebhookError):
    def __init__(self, event_id: UUID) -> None:
        self.event_id = event_id
        message = f"Event with ID {event_id} is not successful."
        super().__init__(message)


# ── Endpoint management ──


async def list_endpoints(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    workspace_id: Sequence[UUID] | None,
    pagination: PaginationParams,
) -> tuple[Sequence[WebhookEndpoint], int]:
    repository = WebhookEndpointRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject).order_by(
        WebhookEndpoint.created_at.desc()
    )
    statement = repository.apply_list_filters(statement, workspace_id=workspace_id)
    return await repository.paginate(
        statement, limit=pagination.limit, page=pagination.page
    )


async def get_endpoint(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> WebhookEndpoint | None:
    repository = WebhookEndpointRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject).where(
        WebhookEndpoint.id == id
    )
    return await repository.get_one_or_none(statement)


async def create_endpoint(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    create_schema: WebhookEndpointCreate,
) -> WebhookEndpoint:
    repository = WebhookEndpointRepository.from_session(session)
    workspace = await get_payload_workspace(session, auth_subject, create_schema)
    if create_schema.secret is not None:
        secret = create_schema.secret
    else:
        secret = generate_token(prefix=WEBHOOK_SECRET_PREFIX)

    endpoint = await repository.create(
        WebhookEndpoint(
            **create_schema.model_dump(exclude={"secret"}, by_alias=True),
            secret=secret,
            workspace=workspace,
        )
    )

    return endpoint


async def update_endpoint(
    session: AsyncSession,
    *,
    endpoint: WebhookEndpoint,
    update_schema: WebhookEndpointUpdate,
) -> WebhookEndpoint:
    repository = WebhookEndpointRepository.from_session(session)
    return await repository.update(
        endpoint,
        update_dict=update_schema.model_dump(exclude_unset=True, exclude_none=True),
    )


async def reset_endpoint_secret(
    session: AsyncSession, *, endpoint: WebhookEndpoint
) -> WebhookEndpoint:
    repository = WebhookEndpointRepository.from_session(session)
    return await repository.update(
        endpoint,
        update_dict={
            "secret": generate_token(prefix=WEBHOOK_SECRET_PREFIX),
        },
    )


async def delete_endpoint(
    session: AsyncSession,
    endpoint: WebhookEndpoint,
) -> WebhookEndpoint:
    repository = WebhookEndpointRepository.from_session(session)
    return await repository.soft_delete(endpoint)


# ── Queries ──


async def list_deliveries(
    session: AsyncReadSession,
    auth_subject: AuthPrincipal[User | Workspace],
    *,
    endpoint_id: Sequence[UUID] | None = None,
    start_timestamp: datetime.datetime | None = None,
    end_timestamp: datetime.datetime | None = None,
    succeeded: bool | None = None,
    query: str | None = None,
    http_code_class: Literal["2xx", "3xx", "4xx", "5xx"] | None = None,
    event_type: Sequence[WebhookEventType] | None = None,
    pagination: PaginationParams,
) -> tuple[Sequence[WebhookDelivery], int]:
    repository = WebhookDeliveryRepository.from_session(session)

    statement = (
        repository.get_readable_statement(auth_subject)
        .options(joinedload(WebhookDelivery.webhook_event))
        .order_by(desc(WebhookDelivery.created_at))
    )
    statement = repository.apply_list_filters(
        statement,
        endpoint_id=endpoint_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        succeeded=succeeded,
        query=query,
        http_code_class=http_code_class,
        event_type=event_type,
    )
    return await repository.paginate(
        statement, limit=pagination.limit, page=pagination.page
    )


# ── Delivery ──


async def redeliver_event(
    session: AsyncSession,
    auth_subject: AuthPrincipal[User | Workspace],
    id: UUID,
) -> None:
    repository = WebhookEventRepository.from_session(session)
    statement = repository.get_readable_statement(auth_subject).where(
        WebhookEvent.id == id
    )
    event = await repository.get_one_or_none(statement)

    if event is None:
        raise ResourceNotFound()

    dispatch_task("webhook_event.send", webhook_event_id=event.id, redeliver=True)


async def on_event_success(session: AsyncSession, id: UUID) -> None:
    """Hook for webhook event delivery success.

    Validates event state (raises on missing/failed events).
    Currently a no-op after MoR removal — kept as an extension point
    for future post-delivery logic (e.g., delivery confirmations).
    """
    repository = WebhookEventRepository.from_session(session)
    event = await repository.get_by_id(id, options=repository.get_eager_options())
    if event is None:
        raise EventDoesNotExist(id)

    if not event.succeeded:
        raise EventNotSuccessful(id)


async def on_event_failed(session: AsyncSession, id: UUID) -> None:
    """
    Helper to hook into the event failed event.

    Detects consecutive failures and disables the endpoint if threshold is exceeded.
    """
    webhook_event_repository = WebhookEventRepository.from_session(session)
    event = await webhook_event_repository.get_by_id(
        id, options=webhook_event_repository.get_eager_options()
    )
    if event is None:
        raise EventDoesNotExist(id)

    if event.succeeded is not False:
        return

    endpoint = event.webhook_endpoint
    if not endpoint.enabled:
        return

    # Get recent events to count the streak
    recent_events = await webhook_event_repository.get_recent_by_endpoint(
        endpoint.id, limit=settings.WEBHOOK_FAILURE_THRESHOLD
    )

    # Check if all recent events are failures
    if len(recent_events) >= settings.WEBHOOK_FAILURE_THRESHOLD and all(
        event.succeeded is False for event in recent_events
    ):
        _log.warning(
            "Disabling webhook endpoint due to consecutive failures",
            webhook_endpoint_id=endpoint.id,
            failure_count=len(recent_events),
        )
        webhook_endpoint_repository = WebhookEndpointRepository.from_session(session)
        await webhook_endpoint_repository.update(
            endpoint, update_dict={"enabled": False}, flush=True
        )

        # Mark all pending events as skipped (bulk UPDATE)
        skipped_count = await webhook_event_repository.skip_pending_by_endpoint(
            endpoint.id
        )

        if skipped_count > 0:
            _log.info(
                "Marked pending events as skipped",
                webhook_endpoint_id=endpoint.id,
                count=skipped_count,
            )

        # Send email to all workspace members
        workspace_id = endpoint.workspace_id
        workspace_memberships = await workspace_membership_service.list_by_workspace(
            session, workspace_id
        )

        if workspace_memberships:
            # User and Workspace are eagerly loaded
            workspace = workspace_memberships[0].workspace
            dashboard_url = f"{settings.FRONTEND_BASE_URL}/dashboard/{workspace.slug}/settings/webhooks"

            for user_org in workspace_memberships:
                user = user_org.user
                email = EmailAdapter.validate_python(
                    {
                        "template": "webhook_endpoint_disabled",
                        "props": {
                            "email": user.email,
                            "workspace": workspace,
                            "webhook_endpoint_url": endpoint.url,
                            "dashboard_url": dashboard_url,
                        },
                    }
                )

                body = render_email_template(email)

                enqueue_email(
                    to_email_addr=user.email,
                    subject=f"Webhook endpoint disabled for {workspace.name}",
                    html_content=body,
                )


async def is_latest_event(session: AsyncSession, event: WebhookEvent) -> bool:
    age_limit = now_utc() - datetime.timedelta(minutes=1)
    repository = WebhookEventRepository.from_session(session)
    count = await repository.count_undelivered_older_than(
        endpoint_id=event.webhook_endpoint_id,
        event_id=event.id,
        before=event.created_at,
        age_limit=age_limit,
    )
    return count == 0


# ── Event creation ──


async def send(
    session: AsyncSession,
    target: Workspace,
    event: WebhookEventType,
    data: object,
) -> list[WebhookEvent]:
    now = now_utc()
    payload = WebhookPayloadTypeAdapter.validate_python(
        {"type": event, "timestamp": now, "data": data}
    )

    event_repository = WebhookEventRepository.from_session(session)
    events: list[WebhookEvent] = []
    for endpoint in await _get_event_target_endpoints(
        session, event=event, target=target
    ):
        try:
            payload_data = payload.get_payload(endpoint.format, target)
            event_type = WebhookEvent(
                created_at=payload.timestamp,
                webhook_endpoint=endpoint,
                type=event,
                payload=payload_data,
            )
            await event_repository.create(event_type, flush=True)
            events.append(event_type)
            dispatch_task("webhook_event.send", webhook_event_id=event_type.id)
        except UnsupportedTarget as e:
            # Log the error but do not raise to not fail the whole request
            _log.error(e.message)
            continue
        except SkipEvent:
            continue

    return events


async def archive_events(
    session: AsyncSession,
    older_than: datetime.datetime,
    batch_size: int = 5000,
) -> None:
    _log.debug("Archive webhook events", older_than=older_than, batch_size=batch_size)
    repository = WebhookEventRepository.from_session(session)

    while True:
        updated_count = await repository.archive_payloads(older_than, batch_size)

        _log.debug("Archived webhook events batch", updated_count=updated_count)

        if updated_count < batch_size:
            break


async def _get_event_target_endpoints(
    session: AsyncSession,
    *,
    event: WebhookEventType,
    target: Workspace,
) -> Sequence[WebhookEndpoint]:
    repository = WebhookEndpointRepository.from_session(session)
    return await repository.get_active_for_event(event, target.id)
