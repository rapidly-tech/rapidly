"""Workspace membership request/response models.

Defines the ``WorkspaceMember`` read model (with nested user fields)
and the ``WorkspaceMemberInvite`` input for inviting new members.
"""

from datetime import datetime
from uuid import UUID

from pydantic import AliasPath, Field

from rapidly.core.email import EmailStrDNS
from rapidly.core.types import Schema

# ---------------------------------------------------------------------------
# Read model
# ---------------------------------------------------------------------------


class WorkspaceMember(Schema):
    user_id: UUID = Field(
        validation_alias=AliasPath("user", "id"),
        description="The ID of the user.",
    )
    created_at: datetime = Field(
        description="The time the WorkspaceMember was created."
    )
    email: str = Field(validation_alias=AliasPath("user", "email"))
    avatar_url: str | None = Field(validation_alias=AliasPath("user", "avatar_url"))
    is_admin: bool = Field(
        default=False,
        description="Whether the user is an admin of the workspace.",
    )


# ---------------------------------------------------------------------------
# Mutation payload
# ---------------------------------------------------------------------------


class WorkspaceMemberInvite(Schema):
    email: EmailStrDNS = Field(description="Email address of the user to invite")
