"""Pydantic schemas for payment listing and detail responses.

Covers the ``Payment`` read model with processor metadata, card /
bank details, risk assessment, and decline information.
"""

from typing import Annotated, Any, Literal

from fastapi import Path
from pydantic import UUID4, Field, TypeAdapter

from rapidly.core.types import (
    WORKSPACE_ID_EXAMPLE,
    AuditableSchema,
    IdentifiableSchema,
    Schema,
    SetSchemaReference,
)
from rapidly.enums import PaymentProcessor
from rapidly.models.payment import PaymentStatus

PaymentID = Annotated[UUID4, Path(description="The payment ID.")]


class PaymentBase(IdentifiableSchema, AuditableSchema):
    processor: PaymentProcessor = Field(
        description="The payment processor.", examples=[PaymentProcessor.stripe]
    )
    status: PaymentStatus = Field(
        description="The payment status.", examples=[PaymentStatus.succeeded]
    )
    amount: int = Field(description="The payment amount in cents.", examples=[1000])
    currency: str = Field(
        description="The payment currency. Currently, only `usd` is supported.",
        examples=["usd"],
    )
    method: str = Field(description="The payment method used.", examples=["card"])
    decline_reason: str | None = Field(
        description="Error code, if the payment was declined.",
        examples=["insufficient_funds"],
    )
    decline_message: str | None = Field(
        description="Human-reasable error message, if the payment was declined.",
        examples=["Your card has insufficient funds."],
    )
    workspace_id: UUID4 = Field(
        description="The ID of the workspace that owns the payment.",
        examples=[WORKSPACE_ID_EXAMPLE],
    )
    processor_metadata: dict[str, Any] = Field(
        description="Additional metadata from the payment processor for internal use.",
        default_factory=dict,
    )


class GenericPayment(PaymentBase):
    """Schema of a payment with a generic payment method."""


class CardPaymentMetadata(Schema):
    """Additional metadata for a card payment method."""

    brand: str = Field(
        description="The brand of the card used for the payment.",
        examples=["visa", "amex"],
    )
    last4: str = Field(
        description="The last 4 digits of the card number.", examples=["4242"]
    )


class CardPayment(PaymentBase):
    """Schema of a payment with a card payment method."""

    method: Literal["card"] = Field(
        description="The payment method used.", examples=["card"]
    )
    method_metadata: CardPaymentMetadata = Field(
        description="Additional metadata for the card payment method."
    )


Payment = Annotated[CardPayment | GenericPayment, SetSchemaReference("Payment")]

PaymentAdapter: TypeAdapter[Payment] = TypeAdapter(Payment)
