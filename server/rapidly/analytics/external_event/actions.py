"""Idempotent ingestion of external webhook events (Stripe, etc.)."""

import contextlib
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

from rapidly.core.utils import now_utc
from rapidly.errors import RapidlyError
from rapidly.models import ExternalEvent
from rapidly.models.external_event import ExternalEventSource, StripeEvent
from rapidly.postgres import AsyncSession
from rapidly.worker import dispatch_task

from .queries import ExternalEventRepository

# ── Errors ────────────────────────────────────────────────────────────


class ExternalEventError(RapidlyError): ...


class ExternalEventDoesNotExist(ExternalEventError):
    def __init__(self, event_id: uuid.UUID) -> None:
        self.event_id = event_id
        super().__init__(f"External event {event_id} not found")


class ExternalEventAlreadyHandled(ExternalEventError):
    def __init__(self, event_id: uuid.UUID) -> None:
        self.event_id = event_id
        super().__init__(f"External event {event_id} already processed")


# ── Service ───────────────────────────────────────────────────────────


async def enqueue(
    session: AsyncSession,
    source: ExternalEventSource,
    task_name: str,
    external_id: str,
    data: dict[str, Any],
) -> ExternalEvent:
    """Store the event (idempotent) and enqueue its processing task."""
    repo = ExternalEventRepository.from_session(session)

    if existing := await repo.get_by_source_and_external_id(source, external_id):
        return existing

    event = await repo.create(
        ExternalEvent(
            source=source, task_name=task_name, external_id=external_id, data=data
        ),
        flush=True,
    )
    dispatch_task(task_name, event.id)
    return event


async def resend(event: ExternalEvent) -> None:
    """Re-dispatch a previously unhandled event."""
    if event.is_handled:
        raise ExternalEventAlreadyHandled(event.id)
    dispatch_task(event.task_name, event.id)


@contextlib.asynccontextmanager
async def handle(
    session: AsyncSession, source: ExternalEventSource, event_id: uuid.UUID
) -> AsyncIterator[ExternalEvent]:
    """Context manager that marks the event as handled on successful exit.

    Uses SELECT ... FOR UPDATE to prevent two concurrent workers from
    processing the same event simultaneously (race-condition guard).
    """
    repo = ExternalEventRepository.from_session(session)
    event = await repo.get_by_source_and_id(source, event_id, with_for_update=True)
    if event is None:
        raise ExternalEventDoesNotExist(event_id)
    if event.is_handled:
        raise ExternalEventAlreadyHandled(event_id)

    yield event
    await repo.update(event, update_dict={"handled_at": now_utc()})


@contextlib.asynccontextmanager
async def handle_stripe(
    session: AsyncSession, event_id: uuid.UUID
) -> AsyncIterator[StripeEvent]:
    """Convenience wrapper for Stripe-sourced events."""
    async with handle(session, ExternalEventSource.stripe, event_id) as event:
        yield cast(StripeEvent, event)
