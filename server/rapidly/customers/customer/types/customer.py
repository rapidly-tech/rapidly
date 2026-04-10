"""Pydantic schemas for customer CRUD, external-ID linking, and avatar URLs.

Defines ``CustomerCreate``, ``CustomerUpdate``, and the read model
``Customer`` with a computed Gravatar avatar derived from the
customer's email address.  Also includes ``CustomerWithMembers`` for
endpoints that inline the associated member list.
"""

import hashlib
from datetime import datetime
from typing import Annotated

from annotated_types import MaxLen
from fastapi import Path
from pydantic import UUID4, Field, computed_field

from rapidly.config import settings
from rapidly.core.address import Address, AddressInput
from rapidly.core.email import EmailStrDNS
from rapidly.core.metadata import (
    MetadataInputMixin,
    MetadataOutputMixin,
)
from rapidly.core.types import (
    CUSTOMER_ID_EXAMPLE,
    WORKSPACE_ID_EXAMPLE,
    AuditableSchema,
    EmptyStrToNoneValidator,
    IdentifiableSchema,
    Schema,
)
from rapidly.identity.member import Member, OwnerCreate
from rapidly.models.customer import CustomerType
from rapidly.platform.workspace.types import WorkspaceID

CustomerID = Annotated[UUID4, Path(description="The customer ID.")]
ExternalCustomerID = Annotated[str, Path(description="The customer external ID.")]

_external_id_description = (
    "The ID of the customer in your system. "
    "This must be unique within the workspace. "
    "Once set, it can't be updated."
)
_external_id_example = "usr_1337"
_email_description = (
    "The email address of the customer. This must be unique within the workspace."
)
_email_example = "customer@example.com"
_name_description = "The name of the customer."
_name_example = "John Doe"

# ── Request schemas ──

CustomerNameInput = Annotated[
    str,
    MaxLen(256),
    Field(description=_name_description, examples=[_name_example]),
    EmptyStrToNoneValidator,
]


class CustomerCreate(MetadataInputMixin, Schema):
    external_id: Annotated[str | None, EmptyStrToNoneValidator] = Field(
        default=None,
        description=_external_id_description,
        examples=[_external_id_example],
    )
    email: EmailStrDNS = Field(
        description=_email_description, examples=[_email_example]
    )
    name: CustomerNameInput | None = None
    billing_address: AddressInput | None = None
    type: CustomerType | None = Field(
        default=None,
        description=(
            "The type of customer. "
            "Defaults to 'individual'. "
            "Set to 'team' for customers that can have multiple members."
        ),
        examples=["individual"],
    )
    workspace_id: WorkspaceID | None = Field(
        default=None,
        description=(
            "The ID of the workspace owning the customer. "
            "**Required unless you use an workspace token.**"
        ),
    )
    owner: OwnerCreate | None = Field(
        default=None,
        description=(
            "Optional owner member to create with the customer. "
            "If not provided, an owner member will be automatically created "
            "using the customer's email and name."
        ),
    )


class CustomerUpdateBase(MetadataInputMixin, Schema):
    email: EmailStrDNS | None = Field(
        default=None, description=_email_description, examples=[_email_example]
    )
    name: CustomerNameInput | None = None
    billing_address: AddressInput | None = None


class CustomerUpdate(CustomerUpdateBase):
    external_id: Annotated[str | None, EmptyStrToNoneValidator] = Field(
        default=None,
        description=_external_id_description,
        examples=[_external_id_example],
    )
    type: CustomerType | None = Field(
        default=None,
        description=(
            "The customer type. "
            "Can only be upgraded from 'individual' to 'team', never downgraded."
        ),
        examples=["team"],
    )


class CustomerUpdateExternalID(CustomerUpdateBase): ...


# ── Response schemas ──


class CustomerBase(MetadataOutputMixin, AuditableSchema, IdentifiableSchema):
    id: UUID4 = Field(
        description="The ID of the customer.", examples=[CUSTOMER_ID_EXAMPLE]
    )
    external_id: str | None = Field(
        description=_external_id_description, examples=[_external_id_example]
    )
    email: str = Field(description=_email_description, examples=[_email_example])
    email_verified: bool = Field(
        description=(
            "Whether the customer email address is verified. "
            "The address is automatically verified when the customer accesses "
            "the customer portal using their email address."
        ),
        examples=[True],
    )
    type: CustomerType | None = Field(
        default=None,
        description=(
            "The type of customer: 'individual' for single users, "
            "'team' for customers with multiple members. "
            "Legacy customers may have NULL type which is treated as 'individual'."
        ),
        examples=["individual"],
    )
    name: str | None = Field(description=_name_description, examples=[_name_example])
    billing_address: Address | None
    workspace_id: UUID4 = Field(
        description="The ID of the workspace owning the customer.",
        examples=[WORKSPACE_ID_EXAMPLE],
    )

    deleted_at: datetime | None = Field(
        description="Timestamp for when the customer was soft deleted."
    )

    @computed_field(examples=["https://www.gravatar.com/avatar/xxx?d=404"])
    def avatar_url(self) -> str:
        domain = self.email.split("@")[-1].lower()

        if (
            not settings.LOGO_DEV_PUBLISHABLE_KEY
            or domain in settings.PERSONAL_EMAIL_DOMAINS
        ):
            email_hash = hashlib.sha256(self.email.lower().encode()).hexdigest()
            return f"https://www.gravatar.com/avatar/{email_hash}?d=404"

        return f"https://img.logo.dev/{domain}?size=64&retina=true&token={settings.LOGO_DEV_PUBLISHABLE_KEY}&fallback=404"


class Customer(CustomerBase):
    """A customer in an workspace."""


class CustomerWithMembers(Customer):
    """A customer in an workspace with their members loaded."""

    members: list[Member] = Field(
        default_factory=list,
        description="List of members belonging to this customer.",
    )
