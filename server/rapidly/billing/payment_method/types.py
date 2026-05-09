"""Pydantic schemas for payment method operations."""

from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from rapidly.core.http import get_safe_return_url
from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.enums import PaymentProcessor


class PaymentMethodSchema(IdentifiableSchema, AuditableSchema):
    """Read-model for a saved payment method."""

    processor: PaymentProcessor
    type: str = Field(description="Payment method type (card, us_bank_account, etc.)")
    brand: str | None = Field(default=None, description="Card brand (visa, mastercard)")
    last4: str | None = Field(default=None, description="Last 4 digits")
    exp_month: int | None = Field(default=None, description="Expiration month")
    exp_year: int | None = Field(default=None, description="Expiration year")
    is_default: bool = Field(
        default=False, description="Whether this is the default PM"
    )


class PaymentMethodCreate(Schema):
    """Request body for adding a new payment method via SetupIntent."""

    confirmation_token_id: str = Field(
        description="Stripe.js confirmation token for the new payment method"
    )
    set_default: bool = Field(
        default=True,
        description="Whether to set this as the default payment method",
    )
    return_url: Annotated[str, AfterValidator(get_safe_return_url)] = Field(
        description="URL to redirect to after 3D Secure verification"
    )


class PaymentMethodConfirm(Schema):
    """Request body to confirm a payment method after 3D Secure."""

    setup_intent_id: str = Field(
        description="The SetupIntent ID returned from the requires_action step"
    )
    set_default: bool = Field(
        default=True,
        description="Whether to set this as the default payment method",
    )


class PaymentMethodCreateSucceededResponse(Schema):
    """Response when payment method was saved successfully."""

    status: Literal["succeeded"] = "succeeded"
    payment_method: PaymentMethodSchema


class PaymentMethodCreateRequiresActionResponse(Schema):
    """Response when additional verification (3D Secure) is needed."""

    status: Literal["requires_action"] = "requires_action"
    client_secret: str = Field(
        description="SetupIntent client_secret for frontend to complete verification"
    )


PaymentMethodCreateResponse = (
    PaymentMethodCreateSucceededResponse | PaymentMethodCreateRequiresActionResponse
)
