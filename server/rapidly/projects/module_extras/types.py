"""Pydantic schemas for module-member + module-link endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, AnyUrl, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

ProjectModuleMemberID = Annotated[
    UUID4, Path(description="The project-module-member ID.")
]
ProjectModuleLinkID = Annotated[UUID4, Path(description="The project-module-link ID.")]


# ── Members ──────────────────────────────────────────────────────────


class ProjectModuleMember(IdentifiableSchema, AuditableSchema):
    module_id: UUID4
    user_id: UUID4


class ProjectModuleMemberCreate(Schema):
    module_id: UUID4 = Field(..., description="The module to assign the user to.")
    user_id: UUID4 = Field(
        ...,
        description=(
            "The user. Must be a member of the project's workspace (the "
            "module's parent project's workspace)."
        ),
    )


# ── Links ────────────────────────────────────────────────────────────


class ProjectModuleLink(IdentifiableSchema, AuditableSchema):
    module_id: UUID4
    created_by_id: UUID4 | None
    url: str
    title: str | None


class ProjectModuleLinkCreate(Schema):
    module_id: UUID4 = Field(..., description="The module the link belongs to.")
    url: AnyUrl = Field(..., description="Absolute URL — http/https only.")
    title: str | None = Field(None, max_length=255)


class ProjectModuleLinkUpdate(Schema):
    url: AnyUrl | None = None
    title: str | None = Field(None, max_length=255)
