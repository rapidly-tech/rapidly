"""Pydantic schemas for project deploy-board endpoints."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import UUID4, Field

from rapidly.core.types import AuditableSchema, IdentifiableSchema, Schema

ProjectDeployBoardID = Annotated[UUID4, Path(description="The deploy-board ID.")]


class ProjectDeployBoard(IdentifiableSchema, AuditableSchema):
    project_id: UUID4
    is_public: bool
    show_comments: bool
    show_reactions: bool
    show_votes: bool
    show_intake_form: bool
    view_props: dict[str, Any]
    # Token is *not* surfaced here on purpose — the read response is
    # what the admin sees in the dashboard, and the secret should
    # only ever leak through the explicit ``/{id}/token`` endpoint.


class ProjectDeployBoardWithToken(ProjectDeployBoard):
    """Variant that surfaces the token. Returned only from token-rotation
    and immediate-after-create endpoints; never from list/get."""

    token: str


class ProjectDeployBoardCreate(Schema):
    project_id: UUID4 = Field(..., description="Project to attach the board to.")
    # Public state is set explicitly so creating a board doesn't
    # accidentally expose it.
    is_public: bool = False
    show_comments: bool = False
    show_reactions: bool = False
    show_votes: bool = False
    show_intake_form: bool = False
    view_props: dict[str, Any] = Field(default_factory=dict)


class ProjectDeployBoardUpdate(Schema):
    is_public: bool | None = None
    show_comments: bool | None = None
    show_reactions: bool | None = None
    show_votes: bool | None = None
    show_intake_form: bool | None = None
    view_props: dict[str, Any] | None = None
