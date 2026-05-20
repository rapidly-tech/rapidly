"""Pydantic schemas for project-member invite endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.project_member import ProjectMemberRole
from rapidly.models.project_member_invite import ProjectMemberInviteStatus

ProjectMemberInviteID = Annotated[
    UUID4, Path(description="The project-member-invite ID.")
]


class ProjectMemberInvite(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    invitee_id: UUID4
    invited_by_id: UUID4 | None
    role: ProjectMemberRole
    status: ProjectMemberInviteStatus
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None
    # Token deliberately omitted from the read response; surfacing it
    # would let any reader of the invite list act as the invitee.


class ProjectMemberInviteCreate(Schema):
    project_id: UUID4 = Field(..., description="The project to invite into.")
    invitee_id: UUID4 = Field(
        ..., description="Workspace member to invite. Must be in the same workspace."
    )
    role: ProjectMemberRole = ProjectMemberRole.member


class ProjectMemberInviteAccept(Schema):
    """Accept a pending invite by presenting its token."""

    token: str = Field(..., min_length=1, max_length=64)


class AcceptedInviteResponse(Schema):
    """Minimal projection of the resulting membership after accept.

    Keeps the invite endpoint independent of the project-member
    submodule's schema — callers that need the full ``ProjectMember``
    can re-fetch via ``/project-members/?project_id=...&user_id=...``.
    """

    project_id: UUID4
    user_id: UUID4
    role: ProjectMemberRole
