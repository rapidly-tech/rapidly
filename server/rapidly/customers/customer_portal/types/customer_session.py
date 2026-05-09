"""Customer-portal session request/response models.

Covers OTP code requests, code verification, direct-token creation,
customer disambiguation, and the portal user info response.
"""

from datetime import datetime

from pydantic import UUID4, Field

from rapidly.core.email import EmailStrDNS
from rapidly.core.types import IdentifiableSchema, Schema
from rapidly.customers.customer_portal.actions.customer_session import (
    CustomerSessionCodeInvalidOrExpired,
)

# ---------------------------------------------------------------------------
# OTP request / response
# ---------------------------------------------------------------------------


class CustomerSessionCodeRequest(Schema):
    email: EmailStrDNS
    workspace_id: UUID4
    customer_id: UUID4 | None = Field(
        default=None,
        description=(
            "Optional customer ID for disambiguation when multiple customers "
            "share the same email."
        ),
    )


class CustomerSessionCodeAuthenticateRequest(Schema):
    code: str


class CustomerSessionCodeAuthenticateResponse(Schema):
    token: str


CustomerSessionCodeInvalidOrExpiredResponse = {
    "description": "Invalid or expired verification code.",
    "model": CustomerSessionCodeInvalidOrExpired.schema(),
}


# ---------------------------------------------------------------------------
# Session introspection
# ---------------------------------------------------------------------------


class CustomerCustomerSession(Schema):
    expires_at: datetime
    return_url: str | None


# ---------------------------------------------------------------------------
# Customer disambiguation
# ---------------------------------------------------------------------------


class CustomerSelectionOption(IdentifiableSchema):
    """Minimal customer info for disambiguation when multiple match an email."""

    name: str | None = Field(description="The customer's name, if available.")


class CustomerSelectionRequiredResponse(Schema):
    """Returned when multiple customers share the same email."""

    error: str = "customer_selection_required"
    detail: str = "Multiple customers found for this email. Please select one."
    customers: list[CustomerSelectionOption] = Field(
        description="List of customers to choose from."
    )


# ---------------------------------------------------------------------------
# Authenticated portal user
# ---------------------------------------------------------------------------


class PortalAuthenticatedUser(Schema):
    """Describes the currently authenticated portal user."""

    type: str = Field(description="Type of authenticated user: 'customer' or 'member'")
    name: str | None = Field(description="User's name, if available.")
    email: str = Field(description="User's email address.")
    customer_id: UUID4 = Field(description="Associated customer ID.")
    member_id: UUID4 | None = Field(
        default=None,
        description="Member ID. Only set for members.",
    )
    role: str | None = Field(
        default=None,
        description="Member role (owner, billing_manager, member). Only set for members.",
    )
