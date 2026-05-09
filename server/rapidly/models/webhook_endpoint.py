"""Webhook endpoint model and event-type registry.

Workspaces register webhook endpoints to receive real-time HTTP
callbacks for lifecycle events (customer changes, share updates,
file-sharing sessions, etc.).
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .workspace import Workspace


# ── Event types ────────────────────────────────────────────────────────


class WebhookEventType(StrEnum):
    """All webhook event types emitted by the platform."""

    # Customer lifecycle
    customer_created = "customer.created"
    customer_updated = "customer.updated"
    customer_deleted = "customer.deleted"
    customer_state_changed = "customer.state_changed"

    # Shares
    share_created = "share.created"
    share_updated = "share.updated"

    # Workspace
    workspace_updated = "workspace.updated"

    # File sharing
    file_sharing_session_created = "file_sharing_session.created"
    file_sharing_session_download_completed = "file_sharing_session.download_completed"
    file_sharing_session_expired = "file_sharing_session.expired"
    file_sharing_session_payment_received = "file_sharing_session.payment_received"


CustomerWebhookEventType = Literal[
    WebhookEventType.customer_created,
    WebhookEventType.customer_updated,
    WebhookEventType.customer_deleted,
    WebhookEventType.customer_state_changed,
]


# ── Delivery format ───────────────────────────────────────────────────


class WebhookFormat(StrEnum):
    """Serialisation format for outgoing webhook payloads."""

    raw = "raw"
    discord = "discord"
    slack = "slack"


# ── Endpoint model ────────────────────────────────────────────────────


class WebhookEndpoint(BaseEntity):
    """An workspace's registered HTTP callback URL for webhook delivery."""

    __tablename__ = "webhook_endpoints"

    url: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[WebhookFormat] = mapped_column(String, nullable=False)
    secret: Mapped[str] = mapped_column(String, nullable=False)
    events: Mapped[list[WebhookEventType]] = mapped_column(
        JSONB, nullable=False, default=[]
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")
