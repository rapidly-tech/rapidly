"""Webhook event: a queued payload bound to an endpoint, with archival tracking."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ColumnElement, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models.base import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StringEnum

from .webhook_endpoint import WebhookEventType

if TYPE_CHECKING:
    from .webhook_endpoint import WebhookEndpoint


class WebhookEvent(BaseEntity):
    """A single webhook payload awaiting (or having completed) delivery.

    Events are considered "archived" once their payload is cleared to reclaim
    storage, signalled by ``payload IS NULL``.  A partial index on
    ``created_at`` excludes archived rows to keep scheduling queries fast.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        Index(
            "ix_webhook_events_created_at_non_archived",
            "created_at",
            postgresql_where="payload IS NOT NULL",
        ),
    )

    # -- Event classification ------------------------------------------------

    type: Mapped[WebhookEventType] = mapped_column(
        StringEnum(WebhookEventType), nullable=False, index=True
    )
    payload: Mapped[str | None] = mapped_column(String, nullable=True)

    # -- Delivery outcome ----------------------------------------------------

    last_http_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    succeeded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    skipped: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # -- Endpoint association ------------------------------------------------

    webhook_endpoint_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def webhook_endpoint(cls) -> Mapped["WebhookEndpoint"]:
        return relationship("WebhookEndpoint", lazy="raise")

    # -- Archival detection --------------------------------------------------

    @hybrid_property
    def is_archived(self) -> bool:
        """An event is archived when its payload has been cleared."""
        return self.payload is None

    @is_archived.inplace.expression
    @classmethod
    def _is_archived_expression(cls) -> ColumnElement[bool]:
        return cls.payload.is_(None)
