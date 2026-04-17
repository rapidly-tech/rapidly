"""Pydantic request/response models for the Screen chamber API."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Request bodies ──


class CreateScreenSessionRequest(BaseModel):
    """Body for ``POST /api/v1/screen/session``."""

    title: str | None = Field(
        default=None,
        max_length=120,
        description="Human-readable label shown to guests on the landing.",
    )
    max_viewers: int = Field(
        default=10,
        ge=1,
        le=10,
        description=(
            "Upper bound of concurrent guests. v1 caps at 10 to keep host "
            "upload bandwidth realistic for home networks."
        ),
    )


class MintInviteRequest(BaseModel):
    """Body for ``POST /api/v1/screen/session/{slug}/invite``."""

    secret: str = Field(min_length=1, max_length=256)


class CloseSessionRequest(BaseModel):
    """Body for ``DELETE /api/v1/screen/session/{slug}``."""

    secret: str = Field(min_length=1, max_length=256)


# ── Responses ──


class CreateScreenSessionResponse(BaseModel):
    short_slug: str
    long_slug: str
    secret: str
    # Client-side template — host substitutes {token} per invite.
    invite_template: str
    expires_at: str  # ISO-8601


class MintInviteResponse(BaseModel):
    invite_token: str
    # Pre-built URL the host can copy/share directly.
    invite_url: str


class ScreenSessionPublicView(BaseModel):
    """Unauthenticated read for the guest landing page.

    Deliberately omits secrets, invite tokens, and host identity. Only
    information needed to render the "about to join" screen.
    """

    short_slug: str
    title: str | None
    max_viewers: int
    started_at: str | None
    host_connected: bool
