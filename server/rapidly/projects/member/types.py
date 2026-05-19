"""Pydantic schemas for project-member endpoints."""

from typing import Annotated

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema
from rapidly.models.project_member import ProjectMemberRole

ProjectMemberID = Annotated[UUID4, Path(description="The project-member ID.")]


class ProjectMember(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    user_id: UUID4
    role: ProjectMemberRole


class ProjectMemberCreate(Schema):
    project_id: UUID4 = Field(..., description="Owning project.")
    user_id: UUID4 = Field(..., description="User to add to the project.")
    role: ProjectMemberRole = ProjectMemberRole.member


class ProjectMemberUpdate(Schema):
    role: ProjectMemberRole | None = None
