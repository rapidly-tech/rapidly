"""Webhook endpoint, event, and delivery Pydantic models.

Covers endpoint creation/update inputs, the full ``WebhookEndpoint``
read model, ``WebhookEvent`` tracking records, and ``WebhookDelivery``
entries that record each HTTP delivery attempt.
"""

from typing import Annotated

from pydantic import UUID4, AnyUrl, Field, PlainSerializer, UrlConstraints

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.webhook_endpoint import WebhookEventType, WebhookFormat
from rapidly.platform.workspace.types import WorkspaceID

# ---------------------------------------------------------------------------
# Shared field types
# ---------------------------------------------------------------------------

HttpsUrl = Annotated[
    AnyUrl,
    UrlConstraints(
        max_length=2083,
        allowed_schemes=["https"],
        host_required=True,
    ),
    PlainSerializer(lambda v: str(v), return_type=str),
]

EndpointURL = Annotated[
    HttpsUrl,
    Field(
        description="The URL where the webhook events will be sent.",
        examples=["https://webhook.site/cb791d80-f26e-4f8c-be88-6e56054192b0"],
    ),
]
EndpointFormat = Annotated[
    WebhookFormat,
    Field(description="The format of the webhook payload."),
]
EndpointSecret = Annotated[
    str,
    Field(
        description="The secret used to sign the webhook events.",
        examples=["rapidly_whs_ovyN6cPrTv56AApvzCaJno08SSmGJmgbWilb33N2JuK"],
    ),
]
EndpointEvents = Annotated[
    list[WebhookEventType],
    Field(description="The events that will trigger the webhook."),
]


# ---------------------------------------------------------------------------
# Delivery record
# ---------------------------------------------------------------------------


class WebhookDelivery(IdentifiableSchema, AuditableSchema):
    """An individual HTTP delivery attempt for a webhook event."""

    succeeded: bool = Field(description="Whether the delivery was successful.")
    http_code: int | None = Field(
        description=(
            "The HTTP code returned by the URL. `null` if the endpoint was unreachable."
        ),
    )
    response: str | None = Field(
        description=(
            "The response body returned by the URL, "
            "or the error message if the endpoint was unreachable."
        ),
    )
    webhook_event: "WebhookEvent" = Field(
        description="The webhook event sent by this delivery."
    )


# ---------------------------------------------------------------------------
# Event record
# ---------------------------------------------------------------------------


class WebhookEvent(IdentifiableSchema, AuditableSchema):
    """A webhook event dispatched to an endpoint.

    An event represents something that happened in the system that should
    be delivered to the webhook endpoint.  It can be delivered multiple
    times until it is marked as succeeded, each attempt creating a new
    ``WebhookDelivery``.
    """

    last_http_code: int | None = Field(
        None,
        description=(
            "Last HTTP code returned by the URL. "
            "`null` if no delivery has been attempted or if the endpoint was unreachable."
        ),
    )
    succeeded: bool | None = Field(
        None,
        description=(
            "Whether this event was successfully delivered."
            " `null` if no delivery has been attempted."
        ),
    )
    skipped: bool = Field(
        description="Whether this event was skipped because the webhook endpoint was disabled."
    )
    payload: str | None = Field(description="The payload of the webhook event.")
    type: WebhookEventType = Field(description="The type of the webhook event.")
    is_archived: bool = Field(
        description=(
            "Whether this event is archived. "
            "Archived events can't be redelivered, "
            "and the payload is not accessible anymore."
        ),
    )


# ---------------------------------------------------------------------------
# Endpoint read model
# ---------------------------------------------------------------------------


class WebhookEndpoint(IdentifiableSchema, AuditableSchema):
    """A registered webhook endpoint."""

    url: EndpointURL
    format: EndpointFormat
    secret: EndpointSecret
    workspace_id: UUID4 = Field(
        description="The workspace ID associated with the webhook endpoint."
    )
    events: EndpointEvents
    enabled: bool = Field(
        description="Whether the webhook endpoint is enabled and will receive events."
    )


# ---------------------------------------------------------------------------
# Mutation payloads
# ---------------------------------------------------------------------------


class WebhookEndpointCreate(Schema):
    """Input for creating a new webhook endpoint."""

    url: EndpointURL
    secret: EndpointSecret | None = Field(
        default=None,
        deprecated="The secret is now generated on the backend.",
        min_length=32,
    )
    format: EndpointFormat
    events: EndpointEvents
    workspace_id: WorkspaceID | None = Field(
        None,
        description=(
            "The workspace ID associated with the webhook endpoint. "
            "**Required unless you use an workspace token.**"
        ),
    )


class WebhookEndpointUpdate(Schema):
    """Input for updating an existing webhook endpoint."""

    url: EndpointURL | None = None
    secret: EndpointSecret | None = Field(
        default=None,
        deprecated="The secret is now generated on the backend.",
        min_length=32,
    )
    format: EndpointFormat | None = None
    events: EndpointEvents | None = None
    enabled: bool | None = Field(
        default=None, description="Whether the webhook endpoint is enabled."
    )
