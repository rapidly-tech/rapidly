"""Webhook delivery: an individual HTTP attempt for a given webhook event."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity

if TYPE_CHECKING:
    from .webhook_endpoint import WebhookEndpoint
    from .webhook_event import WebhookEvent


class WebhookDelivery(BaseEntity):
    """Captures the result of a single HTTP request to a webhook endpoint.

    Each ``WebhookEvent`` may produce multiple delivery rows when retries
    are necessary.  The ``succeeded`` flag and ``http_code`` together
    describe the outcome, while ``response`` stores a truncated copy of
    the upstream response body for debugging.
    """

    __tablename__ = "webhook_deliveries"

    # -- Outcome columns (placed first for readability) ----------------------

    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    http_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -- Foreign keys --------------------------------------------------------

    webhook_endpoint_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    webhook_event_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("webhook_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # -- Relationships -------------------------------------------------------

    @declared_attr
    def webhook_endpoint(cls) -> Mapped["WebhookEndpoint"]:
        return relationship("WebhookEndpoint", lazy="raise")

    @declared_attr
    def webhook_event(cls) -> Mapped["WebhookEvent"]:
        return relationship("WebhookEvent", lazy="raise")
