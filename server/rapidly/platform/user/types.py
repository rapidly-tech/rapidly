"""Pydantic schemas for user profile, OAuth accounts, and deletion flow."""

import uuid
from enum import StrEnum
from typing import Annotated, Literal

from fastapi import Depends
from pydantic import UUID4, EmailStr, Field

from rapidly.core.types import AuditableSchema, Schema, UUID4ToStr
from rapidly.identity.auth.scope import Scope
from rapidly.models.user import IdentityVerificationStatus, OAuthPlatform

# ── Profile ───────────────────────────────────────────────────────────


class UserBase(Schema):
    """Minimal user fields shared across multiple response schemas."""

    email: EmailStr
    avatar_url: str | None
    account_id: UUID4 | None


class OAuthAccountRead(AuditableSchema):
    platform: OAuthPlatform
    account_id: str
    account_email: str
    account_username: str | None


class UserRead(UserBase, AuditableSchema):
    id: uuid.UUID
    accepted_terms_of_service: bool
    is_admin: bool
    identity_verified: bool
    identity_verification_status: IdentityVerificationStatus
    oauth_accounts: list[OAuthAccountRead]


class UserIdentityVerification(Schema):
    id: str
    client_secret: str


class UserScopes(Schema):
    scopes: list[Scope]


# ── Signup attribution ────────────────────────────────────────────────

_SIGNUP_INTENTS = Literal["creator"]


class UserSignupAttribution(Schema):
    """Marketing attribution data captured at signup time."""

    intent: _SIGNUP_INTENTS | None = None

    # Source tracking
    from_storefront: UUID4ToStr | None = None

    # Referrer
    path: str | None = None
    host: str | None = None

    # UTM parameters
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None

    campaign: str | None = None


async def _parse_attribution_query(
    attribution: str | None = None,
) -> UserSignupAttribution | None:
    if attribution:
        return UserSignupAttribution.model_validate_json(attribution)
    return None


UserSignupAttributionQuery = Annotated[
    UserSignupAttribution | None, Depends(_parse_attribution_query)
]

# ── Account deletion ─────────────────────────────────────────────────


class UserDeletionBlockedReason(StrEnum):
    HAS_ACTIVE_WORKSPACES = "has_active_workspaces"


class BlockingWorkspace(Schema):
    id: UUID4
    slug: str
    name: str


class UserDeletionResponse(Schema):
    deleted: bool = Field(description="Whether the account was deleted immediately")
    blocked_reasons: list[UserDeletionBlockedReason] = Field(default_factory=list)
    blocking_workspaces: list[BlockingWorkspace] = Field(default_factory=list)
