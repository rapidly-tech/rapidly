"""Pydantic schemas for workspace access token requests and responses."""

from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import UUID4

from rapidly.core.types import AuditableSchema, Schema
from rapidly.identity.auth.scope import RESERVED_SCOPES, Scope
from rapidly.platform.workspace.types import WorkspaceID

AvailableScope = StrEnum(  # type: ignore
    "AvailableScope", {s: s.value for s in Scope if s not in RESERVED_SCOPES}
)


class WorkspaceAccessTokenCreate(Schema):
    workspace_id: UUID4 | None = None
    comment: str
    expires_in: timedelta | None = None
    scopes: list[AvailableScope]  # pyright: ignore


class WorkspaceAccessTokenUpdate(Schema):
    comment: str | None = None
    scopes: list[AvailableScope] | None = None  # pyright: ignore


class WorkspaceAccessToken(AuditableSchema):
    id: UUID4
    scopes: list[Scope]
    expires_at: datetime | None
    comment: str
    last_used_at: datetime | None
    workspace_id: WorkspaceID


class WorkspaceAccessTokenCreateResponse(Schema):
    workspace_access_token: WorkspaceAccessToken
    token: str
