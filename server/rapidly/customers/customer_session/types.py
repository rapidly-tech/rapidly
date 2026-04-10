"""Customer-session creation and token exchange models.

Covers the ``CustomerSessionCreate`` discriminated union (by customer ID
or external ID), the token-response model, and the full session read model.
"""

from datetime import datetime
from typing import Annotated

from pydantic import UUID4, Field, HttpUrl
from pydantic.aliases import AliasChoices

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.customers.customer.types.customer import Customer

# ---------------------------------------------------------------------------
# Creation payloads
# ---------------------------------------------------------------------------


class CustomerSessionCreateBase(Schema):
    return_url: Annotated[
        HttpUrl | None,
        Field(
            description=(
                "When set, a back button will be shown in the customer portal "
                "to return to this URL."
            ),
            examples=["https://example.com/account"],
        ),
    ] = None
    member_id: UUID4 | None = Field(
        default=None,
        description=(
            "ID of the member to create a session for. "
            "Only applicable when member_model_enabled is True."
        ),
    )
    external_member_id: str | None = Field(
        default=None,
        description=(
            "External ID of the member to create a session for. "
            "Only applicable when member_model_enabled is True."
        ),
    )


class CustomerSessionCustomerIDCreate(CustomerSessionCreateBase):
    """Create session using a customer ID."""

    customer_id: UUID4 = Field(
        description="ID of the customer to create a session for."
    )


class CustomerSessionCustomerExternalIDCreate(CustomerSessionCreateBase):
    """Create session using an external customer ID."""

    external_customer_id: str = Field(
        description="External ID of the customer to create a session for.",
        validation_alias=AliasChoices("external_customer_id", "customer_external_id"),
    )


CustomerSessionCreate = (
    CustomerSessionCustomerIDCreate | CustomerSessionCustomerExternalIDCreate
)


# ---------------------------------------------------------------------------
# Read model
# ---------------------------------------------------------------------------


class CustomerSession(IdentifiableSchema, AuditableSchema):
    """An authenticated customer session with portal access."""

    token: str = Field(validation_alias="raw_token")
    expires_at: datetime
    return_url: str | None
    customer_portal_url: str
    customer_id: UUID4
    customer: Customer
