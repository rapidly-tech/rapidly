"""System event catalogue and metadata schemas.

Enumerates all platform-generated events (``SystemEvent`` enum) and
their typed metadata payloads (e.g. ``CustomerCreatedMetadata``).
Provides ``emit_system_event`` for dispatching system events with
structured metadata into the event pipeline.
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, NotRequired, overload

from sqlalchemy.orm import Mapped
from sqlalchemy.util.typing import TypedDict

from rapidly.core.address import AddressDict
from rapidly.models import Customer, Event, Workspace
from rapidly.models.event import EventSource

# ── System event names ──


class SystemEvent(StrEnum):
    customer_created = "customer.created"
    customer_updated = "customer.updated"
    customer_deleted = "customer.deleted"


# ── Labels ──

SYSTEM_EVENT_LABELS: dict[str, str] = {
    "customer.created": "Customer Created",
    "customer.updated": "Customer Updated",
    "customer.deleted": "Customer Deleted",
}


class CustomerCreatedMetadata(TypedDict):
    customer_id: str
    customer_email: str
    customer_name: str | None
    customer_external_id: str | None


class CustomerCreatedEvent(Event):
    if TYPE_CHECKING:
        source: Mapped[Literal[EventSource.system]]
        name: Mapped[Literal[SystemEvent.customer_created]]
        user_metadata: Mapped[CustomerCreatedMetadata]  # type: ignore[assignment]


class CustomerUpdatedFields(TypedDict):
    name: NotRequired[str | None]
    email: NotRequired[str | None]
    billing_address: NotRequired[AddressDict | None]
    metadata: NotRequired[dict[str, str | int | bool] | None]


class CustomerUpdatedMetadata(TypedDict):
    customer_id: str
    customer_email: str
    customer_name: str | None
    customer_external_id: str | None
    updated_fields: CustomerUpdatedFields


class CustomerUpdatedEvent(Event):
    if TYPE_CHECKING:
        source: Mapped[Literal[EventSource.system]]
        name: Mapped[Literal[SystemEvent.customer_updated]]
        user_metadata: Mapped[CustomerUpdatedMetadata]  # type: ignore[assignment]


class CustomerDeletedMetadata(TypedDict):
    customer_id: str
    customer_email: str
    customer_name: str | None
    customer_external_id: str | None


class CustomerDeletedEvent(Event):
    if TYPE_CHECKING:
        source: Mapped[Literal[EventSource.system]]
        name: Mapped[Literal[SystemEvent.customer_deleted]]
        user_metadata: Mapped[CustomerDeletedMetadata]  # type: ignore[assignment]


@overload
def build_system_event(
    name: Literal[SystemEvent.customer_created],
    customer: Customer,
    workspace: Workspace,
    metadata: CustomerCreatedMetadata,
) -> Event: ...


@overload
def build_system_event(
    name: Literal[SystemEvent.customer_updated],
    customer: Customer,
    workspace: Workspace,
    metadata: CustomerUpdatedMetadata,
) -> Event: ...


@overload
def build_system_event(
    name: Literal[SystemEvent.customer_deleted],
    customer: Customer,
    workspace: Workspace,
    metadata: CustomerDeletedMetadata,
) -> Event: ...


def build_system_event(
    name: SystemEvent,
    customer: Customer,
    workspace: Workspace,
    metadata: Any,
) -> Event:
    return Event(
        name=name,
        source=EventSource.system,
        customer_id=customer.id,
        workspace=workspace,
        user_metadata=metadata,
    )
