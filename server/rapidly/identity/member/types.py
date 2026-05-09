"""Pydantic schemas for member CRUD and customer association.

Defines ``MemberCreate``, ``MemberUpdate``, and the read model
``Member`` with role, external ID, and optional customer linkage.
"""

from typing import Annotated

from annotated_types import MaxLen
from pydantic import UUID4, Field

from rapidly.core.email import EmailStrDNS
from rapidly.core.types import (
    AuditableSchema,
    EmptyStrToNoneValidator,
    IdentifiableSchema,
    Schema,
)
from rapidly.models.member import MemberRole

# ── Field metadata ──

_external_id_description = (
    "The ID of the member in your system. This must be unique within the customer. "
)
_external_id_example = "usr_1337"
_email_description = "The email address of the member."
_email_example = "member@example.com"
_name_description = "The name of the member."
_name_example = "Jane Doe"

MemberNameInput = Annotated[
    str,
    MaxLen(256),
    Field(description=_name_description, examples=[_name_example]),
    EmptyStrToNoneValidator,
]


# ── Write schemas ──


class OwnerCreate(Schema):
    """Schema for creating an owner member during customer creation."""

    email: EmailStrDNS | None = Field(
        default=None, description=_email_description, examples=[_email_example]
    )
    name: MemberNameInput | None = None
    external_id: Annotated[str | None, EmptyStrToNoneValidator] = Field(
        default=None,
        description=_external_id_description,
        examples=[_external_id_example],
    )


class MemberCreate(Schema):
    """Schema for creating a new member."""

    customer_id: UUID4 = Field(
        description="The ID of the customer this member belongs to."
    )
    email: EmailStrDNS = Field(
        description=_email_description, examples=[_email_example]
    )
    name: MemberNameInput | None = None
    external_id: Annotated[str | None, EmptyStrToNoneValidator] = Field(
        default=None,
        description=_external_id_description,
        examples=[_external_id_example],
    )
    role: MemberRole = Field(
        default=MemberRole.member,
        description="The role of the member within the customer.",
        examples=[MemberRole.member],
    )


class MemberUpdate(Schema):
    """Schema for updating a member."""

    name: MemberNameInput | None = None
    role: MemberRole | None = Field(
        default=None,
        description="The role of the member within the customer.",
        examples=[MemberRole.member],
    )


# ── Read schemas ──


class MemberBase(AuditableSchema, IdentifiableSchema):
    """Base schema for member responses."""

    id: UUID4 = Field(description="The ID of the member.")
    customer_id: UUID4 = Field(
        description="The ID of the customer this member belongs to."
    )
    email: str = Field(description=_email_description, examples=[_email_example])
    name: str | None = Field(description=_name_description, examples=[_name_example])
    external_id: str | None = Field(
        description=_external_id_description, examples=[_external_id_example]
    )
    role: MemberRole = Field(
        description="The role of the member within the customer.",
        examples=[MemberRole.owner],
    )


class Member(MemberBase):
    """A member of a customer."""

    pass
