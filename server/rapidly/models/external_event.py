"""Inbound events received from third-party integrations.

``ExternalEvent`` is the polymorphic base for all external webhook
payloads.  Concrete subclasses like ``StripeEvent`` add
provider-specific helpers for accessing the deserialized data.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

import stripe as stripe_lib
from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    ColumnElement,
    String,
    UniqueConstraint,
    type_coerce,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from rapidly.core.db.models.base import BaseEntity
from rapidly.core.extensions.sqlalchemy.types import StrEnumType


class ExternalEventSource(StrEnum):
    """Supported upstream webhook providers."""

    stripe = "stripe"


class ExternalEvent(BaseEntity):
    """Base model for inbound third-party webhook payloads.

    A unique constraint on (source, external_id) guarantees
    idempotent ingestion regardless of upstream retry behaviour.
    """

    __tablename__ = "external_events"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    # -- Identification ------------------------------------------------------

    source: Mapped[ExternalEventSource] = mapped_column(
        StrEnumType(ExternalEventSource), nullable=False, index=True
    )
    external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # -- Processing state ----------------------------------------------------

    task_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    handled_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None, index=True
    )

    # -- Payload -------------------------------------------------------------

    data: Mapped[dict[str, Any]] = mapped_column("data", JSONB, nullable=False)

    # -- Convenience predicate -----------------------------------------------

    @hybrid_property
    def is_handled(self) -> bool:
        """Whether this event has been successfully processed."""
        return self.handled_at is not None

    @is_handled.inplace.expression
    @classmethod
    def _is_handled_expression(cls) -> ColumnElement[bool]:
        return type_coerce(cls.handled_at.is_not(None), Boolean)

    # -- Polymorphic dispatch ------------------------------------------------

    __mapper_args__ = {
        "polymorphic_on": "source",
    }


class StripeEvent(ExternalEvent):
    """Stripe webhook event with typed data accessor."""

    source: Mapped[Literal[ExternalEventSource.stripe]] = mapped_column(  # pyright: ignore
        use_existing_column=True, default=ExternalEventSource.stripe
    )

    @property
    def stripe_data(self) -> stripe_lib.Event:
        """Deserialize the raw JSON payload into a Stripe SDK event object."""
        return stripe_lib.Event.construct_from(self.data, key=None)

    __mapper_args__ = {
        "polymorphic_identity": ExternalEventSource.stripe,
        "polymorphic_load": "inline",
    }
