"""Webhook payload builders and dispatch registry.

Maps ``WebhookEventType`` variants to their corresponding model /
schema pairs and provides functions to serialise payloads into JSON,
Discord-embed, and Slack-block formats.  The ``WebhookTypeObject``
union is the canonical list of event→model bindings used at delivery
time.
"""

import inspect
import json
import typing
from datetime import datetime
from inspect import Parameter, Signature
from typing import Annotated, Any, Literal, assert_never, get_args, get_origin

from fastapi import FastAPI
from fastapi.routing import APIRoute
from makefun import with_signature
from pydantic import (
    Discriminator,
    GetJsonSchemaHandler,
    TypeAdapter,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema as cs

from rapidly.catalog.share.types import Share as ShareSchema
from rapidly.core.types import IdentifiableSchema, Schema
from rapidly.customers.customer.types.customer import Customer as CustomerSchema
from rapidly.customers.customer.types.state import CustomerState as CustomerStateSchema
from rapidly.errors import RapidlyError
from rapidly.integrations.discord.webhook import (
    DiscordEmbedField,
    DiscordPayload,
    get_branded_discord_embed,
)
from rapidly.models import (
    Customer,
    Share,
    User,
    Workspace,
)
from rapidly.models.file_share_session import FileShareSession
from rapidly.models.webhook_endpoint import WebhookEventType, WebhookFormat
from rapidly.platform.workspace.types import Workspace as WorkspaceSchema
from rapidly.sharing.file_sharing.types import FileShareSessionSchema

from .slack import SlackPayload, SlackText, get_branded_slack_payload

# ── Event-to-Model Bindings ──

WebhookTypeObject = (
    tuple[Literal[WebhookEventType.customer_created], Customer]
    | tuple[Literal[WebhookEventType.customer_updated], Customer]
    | tuple[Literal[WebhookEventType.customer_deleted], Customer]
    | tuple[Literal[WebhookEventType.customer_state_changed], CustomerStateSchema]
    | tuple[Literal[WebhookEventType.share_created], Share]
    | tuple[Literal[WebhookEventType.share_updated], Share]
    | tuple[Literal[WebhookEventType.workspace_updated], Workspace]
    | tuple[Literal[WebhookEventType.file_sharing_session_created], FileShareSession]
    | tuple[
        Literal[WebhookEventType.file_sharing_session_download_completed],
        FileShareSession,
    ]
    | tuple[Literal[WebhookEventType.file_sharing_session_expired], FileShareSession]
    | tuple[
        Literal[WebhookEventType.file_sharing_session_payment_received],
        FileShareSession,
    ]
)


# ── Errors ──


class UnsupportedTarget(RapidlyError):
    def __init__(
        self,
        target: User | Workspace,
        schema: type["BaseWebhookPayload"],
        format: WebhookFormat,
    ) -> None:
        self.target = target
        self.format = format
        message = f"{schema.__name__} payload does not support target {type(target).__name__} for format {format}"
        super().__init__(message)


class SkipEvent(RapidlyError):
    def __init__(self, event: WebhookEventType, format: WebhookFormat) -> None:
        self.event = event
        self.format = format
        message = f"Skipping event {event} for format {format}"
        super().__init__(message)


# ── Base Payload ──


class BaseWebhookPayload(Schema):
    type: WebhookEventType
    timestamp: datetime
    data: IdentifiableSchema

    def get_payload(self, format: WebhookFormat, target: User | Workspace) -> str:
        match format:
            case WebhookFormat.raw:
                return self.get_raw_payload()
            case WebhookFormat.discord:
                return self.get_discord_payload(target)
            case WebhookFormat.slack:
                return self.get_slack_payload(target)
            case _:
                assert_never(format)

    def get_raw_payload(self) -> str:
        return self.model_dump_json()

    def get_discord_payload(self, target: User | Workspace) -> str:
        # Generic Discord payload, override in subclasses for more specific payloads
        fields: list[DiscordEmbedField] = [
            {"name": "Object", "value": str(self.data.id)},
        ]
        if isinstance(target, User):
            fields.append({"name": "User", "value": target.email})
        elif isinstance(target, Workspace):
            fields.append({"name": "Workspace", "value": target.name})

        payload: DiscordPayload = {
            "content": self.type,
            "embeds": [
                get_branded_discord_embed(
                    {
                        "title": self.type,
                        "description": self.type,
                        "fields": fields,
                    }
                )
            ],
        }

        return json.dumps(payload)

    def get_slack_payload(self, target: User | Workspace) -> str:
        # Generic Slack payload, override in subclasses for more specific payloads
        fields: list[SlackText] = [
            {"type": "mrkdwn", "text": f"*Object*\n{self.data.id}"},
        ]
        if isinstance(target, User):
            fields.append({"type": "mrkdwn", "text": f"*User*\n{target.email}"})
        elif isinstance(target, Workspace):
            fields.append({"type": "mrkdwn", "text": f"*Workspace*\n{target.name}"})

        payload: SlackPayload = get_branded_slack_payload(
            {
                "text": self.type,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": self.type,
                        },
                        "fields": fields,
                    }
                ],
            }
        )

        return json.dumps(payload)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)

        # Force the example of the `type` field to be the event type literal value
        type_field_annotation = cls.model_fields["type"].annotation
        if get_origin(type_field_annotation) is Literal:
            literal_value = get_args(type_field_annotation)[0]
            json_schema["properties"]["type"]["examples"] = [literal_value]

        return json_schema


# ── Customer Event Payloads ──


class WebhookCustomerCreatedPayload(BaseWebhookPayload):
    """
    Sent when a new customer is created.

    A customer can be created:

    * After a successful file sharing payment.
    * Programmatically via the API.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.customer_created]
    data: CustomerSchema


class WebhookCustomerUpdatedPayload(BaseWebhookPayload):
    """
    Sent when a customer is updated.

    This event is fired when the customer details are updated.

    If you want to be notified when a customer's meter state changes, you should listen to the `customer_state_changed` event.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.customer_updated]
    data: CustomerSchema


class WebhookCustomerDeletedPayload(BaseWebhookPayload):
    """
    Sent when a customer is deleted.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.customer_deleted]
    data: CustomerSchema


class WebhookCustomerStateChangedPayload(BaseWebhookPayload):
    """
    Sent when a customer state has changed.

    It's triggered when:

    * Customer is created, updated or deleted.
    * A meter value changes.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.customer_state_changed]
    data: CustomerStateSchema


# ── Share Event Payloads ──


class WebhookShareCreatedPayload(BaseWebhookPayload):
    """
    Sent when a new share is created.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.share_created]
    data: ShareSchema


class WebhookShareUpdatedPayload(BaseWebhookPayload):
    """
    Sent when a share is updated.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.share_updated]
    data: ShareSchema


# ── Workspace Event Payloads ──


class WebhookWorkspaceUpdatedPayload(BaseWebhookPayload):
    """
    Sent when a workspace is updated.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.workspace_updated]
    data: WorkspaceSchema


# ── File Sharing Event Payloads ──


class WebhookFileSharingSessionCreatedPayload(BaseWebhookPayload):
    """
    Sent when a new file sharing session is created.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.file_sharing_session_created]
    data: FileShareSessionSchema


class WebhookFileSharingSessionDownloadCompletedPayload(BaseWebhookPayload):
    """
    Sent when a download is completed for a file sharing session.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.file_sharing_session_download_completed]
    data: FileShareSessionSchema


class WebhookFileSharingSessionExpiredPayload(BaseWebhookPayload):
    """
    Sent when a file sharing session expires.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.file_sharing_session_expired]
    data: FileShareSessionSchema


class WebhookFileSharingSessionPaymentReceivedPayload(BaseWebhookPayload):
    """
    Sent when a payment is received for a file sharing session.

    **Discord & Slack support:** Basic
    """

    type: Literal[WebhookEventType.file_sharing_session_payment_received]
    data: FileShareSessionSchema


# ── Payload Union and Type Adapter ──

WebhookPayload = Annotated[
    WebhookCustomerCreatedPayload
    | WebhookCustomerUpdatedPayload
    | WebhookCustomerDeletedPayload
    | WebhookCustomerStateChangedPayload
    | WebhookShareCreatedPayload
    | WebhookShareUpdatedPayload
    | WebhookWorkspaceUpdatedPayload
    | WebhookFileSharingSessionCreatedPayload
    | WebhookFileSharingSessionDownloadCompletedPayload
    | WebhookFileSharingSessionExpiredPayload
    | WebhookFileSharingSessionPaymentReceivedPayload,
    Discriminator(discriminator="type"),
]
WebhookPayloadTypeAdapter: TypeAdapter[WebhookPayload] = TypeAdapter(WebhookPayload)


# ── Webhook Documentation ──


class WebhookAPIRoute(APIRoute):
    """
    Since FastAPI documents webhook through API routes with a body field,
    we might be in a situation where it generates `-Input` and `-Output` variants
    of the schemas because it sees them as "input" schemas.

    But we don't want that.

    The trick here is to force the body field to be in "serialization" mode, so we
    prevent Pydantic to generate the `-Input` and `-Output` variants.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.body_field is not None:
            self.body_field.mode = "serialization"


def document_webhooks(app: FastAPI) -> None:
    def _endpoint(body: Any) -> None: ...

    webhooks_schemas: tuple[type[BaseWebhookPayload]] = typing.get_args(
        typing.get_args(WebhookPayload)[0]
    )
    for webhook_schema in webhooks_schemas:
        signature = Signature(
            [
                Parameter(
                    name="body",
                    kind=Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=webhook_schema,
                )
            ]
        )

        event_type_annotation = webhook_schema.model_fields["type"].annotation
        event_type: WebhookEventType = get_args(event_type_annotation)[0]

        endpoint = with_signature(signature)(_endpoint)

        app.webhooks.add_api_route(
            event_type,
            endpoint,
            methods=["POST"],
            summary=event_type,
            description=inspect.getdoc(webhook_schema),
            route_class_override=WebhookAPIRoute,
        )
