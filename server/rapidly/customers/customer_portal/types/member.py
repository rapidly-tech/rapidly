"""Pydantic schemas for customer-portal member management.

These schemas represent a team member as seen through the customer
portal -- a subset of the full internal member model.
"""

from pydantic import Field

from rapidly.core.email import EmailStrDNS
from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.member import MemberRole

_ROLE_EXAMPLES = [MemberRole.billing_manager, MemberRole.member]


class CustomerPortalMember(IdentifiableSchema, AuditableSchema):
    """A member of the customer's team as seen in the customer portal."""

    email: str = Field(description="The email address of the member.")
    name: str | None = Field(description="The name of the member.")
    role: MemberRole = Field(description="The role of the member within the team.")


class CustomerPortalMemberCreate(Schema):
    """Payload for adding a new member to the customer's team."""

    email: EmailStrDNS = Field(description="The email address of the new member.")
    name: str | None = Field(default=None, description="Display name (optional).")
    role: MemberRole = Field(
        default=MemberRole.member,
        description="Initial role. Defaults to 'member'.",
        examples=_ROLE_EXAMPLES,
    )


class CustomerPortalMemberUpdate(Schema):
    """Payload for updating an existing member's role."""

    role: MemberRole | None = Field(
        default=None,
        description="The new role for the member.",
        examples=_ROLE_EXAMPLES,
    )
