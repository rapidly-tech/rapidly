"""Pydantic schemas for event ingestion, listing, and statistics responses.

Covers the ``EventCreate`` input model (with timestamp validation),
the ``Event`` read model, time-series statistics envelopes
(``EventsStatistics``), and the discriminated union of system-event
metadata types used for customer lifecycle tracking.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, NotRequired

from fastapi import Path
from pydantic import (
    UUID4,
    AfterValidator,
    AliasChoices,
    AwareDatetime,
    Discriminator,
    Field,
)
from pydantic.type_adapter import TypeAdapter
from typing_extensions import TypedDict

from rapidly.analytics.event.system import (
    CustomerCreatedMetadata,
    CustomerDeletedMetadata,
    CustomerUpdatedMetadata,
)
from rapidly.analytics.event.system import SystemEvent as SystemEventEnum
from rapidly.core.metadata import METADATA_DESCRIPTION, MetadataValue
from rapidly.core.types import (
    ClassName,
    IdentifiableSchema,
    Schema,
    SetSchemaReference,
)
from rapidly.customers.customer.types.customer import Customer
from rapidly.models.event import EventSource
from rapidly.platform.workspace.types import WorkspaceID

# ── Ingest schemas ──

_NAME_DESCRIPTION = "The name of the event."
_SOURCE_DESCRIPTION = (
    "The source of the event. "
    "`system` events are created by Rapidly. "
    "`user` events are the one you create through our ingestion API."
)


def default_timestamp_factory() -> datetime:
    return datetime.now(UTC)


def is_past_timestamp(timestamp: datetime) -> datetime:
    # Convert to UTC
    timestamp = timestamp.astimezone(UTC)
    if timestamp > datetime.now(UTC):
        raise ValueError("Timestamp must be in the past.")
    return timestamp


class CostMetadata(TypedDict):
    amount: Annotated[
        Decimal,
        Field(
            description="The amount in cents.",
            max_digits=17,
            decimal_places=12,
        ),
    ]
    currency: Annotated[
        str,
        Field(
            pattern="usd",
            description="The currency. Currently, only `usd` is supported.",
        ),
    ]


class LLMMetadata(TypedDict):
    vendor: Annotated[str, Field(description="The vendor of the event.")]
    model: Annotated[str, Field(description="The model used for the event.")]
    prompt: Annotated[
        str | None,
        Field(default=None, description="The LLM prompt used for the event."),
    ]
    response: Annotated[
        str | None,
        Field(default=None, description="The LLM response used for the event."),
    ]
    input_tokens: Annotated[
        int,
        Field(description="The number of LLM input tokens used for the event."),
    ]
    cached_input_tokens: Annotated[
        NotRequired[int],
        Field(
            description="The number of LLM cached tokens that were used for the event.",
        ),
    ]
    output_tokens: Annotated[
        int,
        Field(description="The number of LLM output tokens used for the event."),
    ]
    total_tokens: Annotated[
        int,
        Field(description="The total number of LLM tokens used for the event."),
    ]


class EventMetadataInput(  # type: ignore[call-arg]
    TypedDict,
    total=False,
    extra_items=MetadataValue,
):
    _cost: CostMetadata
    _llm: LLMMetadata


def metadata_default_factory() -> EventMetadataInput:
    return {}


class EventCreateBase(Schema):
    timestamp: Annotated[
        AwareDatetime,
        AfterValidator(is_past_timestamp),
    ] = Field(
        default_factory=default_timestamp_factory,
        description="The timestamp of the event.",
    )
    name: str = Field(..., description="The name of the event.")
    workspace_id: WorkspaceID | None = Field(
        default=None,
        description=(
            "The ID of the workspace owning the event. "
            "**Required unless you use an workspace token.**"
        ),
    )
    external_id: str | None = Field(
        default=None,
        description=(
            "Your unique identifier for this event. "
            "Useful for deduplication and parent-child relationships."
        ),
    )
    parent_id: str | None = Field(
        default=None,
        description=(
            "The ID of the parent event. "
            "Can be either a Rapidly event ID (UUID) or an external event ID."
        ),
    )
    metadata: EventMetadataInput = Field(
        description=METADATA_DESCRIPTION.format(
            heading=(
                "Key-value object allowing you to store additional information about the event. "
                "Some keys like `_llm` are structured data that are handled specially by Rapidly."
            )
        ),
        default_factory=metadata_default_factory,
        serialization_alias="user_metadata",
    )


class EventCreateCustomer(EventCreateBase):
    customer_id: UUID4 = Field(
        description=(
            "ID of the customer in your Rapidly workspace associated with the event."
        )
    )
    member_id: UUID4 | None = Field(
        default=None,
        description=(
            "ID of the member within the customer's workspace "
            "who performed the action. Used for member-level attribution in B2B."
        ),
    )


class EventCreateExternalCustomer(EventCreateBase):
    external_customer_id: str = Field(
        description="ID of the customer in your system associated with the event."
    )
    external_member_id: str | None = Field(
        default=None,
        description=(
            "ID of the member in your system within the customer's workspace "
            "who performed the action. Used for member-level attribution in B2B."
        ),
    )


EventCreate = EventCreateCustomer | EventCreateExternalCustomer


class EventsIngest(Schema):
    events: list[EventCreate] = Field(description="List of events to ingest.")


class EventsIngestResponse(Schema):
    inserted: int = Field(description="Number of events inserted.")
    duplicates: int = Field(
        default=0, description="Number of duplicate events skipped."
    )


# ── Response schemas ──


class BaseEvent(IdentifiableSchema):
    timestamp: datetime = Field(description="The timestamp of the event.")
    workspace_id: WorkspaceID = Field(
        description="The ID of the workspace owning the event."
    )
    customer_id: UUID4 | None = Field(
        description=(
            "ID of the customer in your Rapidly workspace associated with the event."
        )
    )
    customer: Customer | None = Field(
        description="The customer associated with the event."
    )
    external_customer_id: str | None = Field(
        description="ID of the customer in your system associated with the event."
    )
    member_id: UUID4 | None = Field(
        default=None,
        description=(
            "ID of the member within the customer's workspace "
            "who performed the action inside B2B."
        ),
    )
    external_member_id: str | None = Field(
        default=None,
        description=(
            "ID of the member in your system within the customer's workspace "
            "who performed the action inside B2B."
        ),
    )
    child_count: int = Field(
        default=0, description="Number of direct child events linked to this event."
    )
    parent_id: UUID4 | None = Field(
        default=None,
        description="The ID of the parent event.",
    )
    label: str = Field(description="Human readable label of the event type.")


class SystemEventBase(BaseEvent):
    """An event created by Rapidly."""

    source: Literal[EventSource.system] = Field(description=_SOURCE_DESCRIPTION)


class CustomerCreatedEvent(SystemEventBase):
    """An event created by Rapidly when a customer is created."""

    name: Literal[SystemEventEnum.customer_created] = Field(
        description=_NAME_DESCRIPTION
    )
    metadata: CustomerCreatedMetadata = Field(
        validation_alias=AliasChoices("user_metadata", "metadata")
    )


class CustomerUpdatedEvent(SystemEventBase):
    """An event created by Rapidly when a customer is updated."""

    name: Literal[SystemEventEnum.customer_updated] = Field(
        description=_NAME_DESCRIPTION
    )
    metadata: CustomerUpdatedMetadata = Field(
        validation_alias=AliasChoices("user_metadata", "metadata")
    )


class CustomerDeletedEvent(SystemEventBase):
    """An event created by Rapidly when a customer is deleted."""

    name: Literal[SystemEventEnum.customer_deleted] = Field(
        description=_NAME_DESCRIPTION
    )
    metadata: CustomerDeletedMetadata = Field(
        validation_alias=AliasChoices("user_metadata", "metadata")
    )


SystemEvent = Annotated[
    CustomerCreatedEvent | CustomerUpdatedEvent | CustomerDeletedEvent,
    Discriminator("name"),
    SetSchemaReference("SystemEvent"),
    ClassName("SystemEvent"),
]


class EventMetadataOutput(  # type: ignore[call-arg]
    TypedDict,
    total=False,
    extra_items=str | int | float | bool,
):
    _cost: CostMetadata
    _llm: LLMMetadata


class UserEvent(BaseEvent):
    """An event you created through the ingestion API."""

    name: str = Field(description=_NAME_DESCRIPTION)
    source: Literal[EventSource.user] = Field(description=_SOURCE_DESCRIPTION)
    metadata: EventMetadataOutput = Field(
        validation_alias=AliasChoices("user_metadata", "metadata")
    )


Event = Annotated[
    SystemEvent | UserEvent,
    Discriminator("source"),
    SetSchemaReference("Event"),
    ClassName("Event"),
]

EventTypeAdapter: TypeAdapter[Event] = TypeAdapter(Event)


# ── Statistics schemas ──


class EventName(Schema):
    name: str = Field(description="The name of the event.")
    source: EventSource = Field(description=_SOURCE_DESCRIPTION)
    occurrences: int = Field(description="Number of times the event has occurred.")
    first_seen: datetime = Field(description="The first time the event occurred.")
    last_seen: datetime = Field(description="The last time the event occurred.")


class EventStatistics(Schema):
    """Aggregate statistics for events grouped by root event name."""

    name: str = Field(description="The name of the root event.")
    label: str = Field(description="The label of the event type.")
    event_type_id: UUID4 = Field(description="The ID of the event type")
    occurrences: int = Field(
        description="Number of root events with this name (i.e., number of traces)."
    )
    customers: int = Field(
        description="Number of distinct customers associated with events."
    )
    totals: dict[str, Decimal] = Field(
        description="Sum of each field across all events in all hierarchies.",
        default_factory=dict,
    )
    averages: dict[str, Decimal] = Field(
        description="Average of per-hierarchy totals (i.e., average cost per trace).",
        default_factory=dict,
    )
    p10: dict[str, Decimal] = Field(
        description="10th percentile of per-hierarchy totals.",
        default_factory=dict,
    )
    p90: dict[str, Decimal] = Field(
        description="90th percentile of per-hierarchy totals.",
        default_factory=dict,
    )
    p99: dict[str, Decimal] = Field(
        description="99th percentile of per-hierarchy totals.",
        default_factory=dict,
    )


class StatisticsPeriod(Schema):
    """Event statistics for a single time period."""

    timestamp: AwareDatetime = Field(description="Period timestamp")
    period_start: AwareDatetime = Field(description="Period start (inclusive)")
    period_end: AwareDatetime = Field(description="Period end (exclusive)")
    stats: list[EventStatistics] = Field(
        description="Stats grouped by event name for this period"
    )


class ListStatisticsTimeseries(Schema):
    """Event statistics timeseries."""

    periods: list[StatisticsPeriod] = Field(description="Stats for each time period.")
    totals: list[EventStatistics] = Field(
        description="Overall stats across all periods."
    )


EventID = Annotated[UUID4, Path(description="The event ID.")]
