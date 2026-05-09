"""Pydantic request/response models for the Call chamber API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Request bodies ──


class CreateCallSessionRequest(BaseModel):
    """Body for ``POST /api/v1/call/session``."""

    title: str | None = Field(
        default=None,
        max_length=120,
        description="Human-readable label shown to other participants on join.",
    )
    max_participants: int = Field(
        default=4,
        ge=2,
        le=4,
        description=(
            "Upper bound of concurrent participants (including the host). "
            "v1 mesh caps at 4 to keep the N² peer-connection count bounded "
            "on home uplinks."
        ),
    )
    mode: Literal["audio_only", "audio_video"] = Field(
        default="audio_video",
        description=(
            "``audio_only`` asks the browser for only microphone access; "
            "``audio_video`` asks for both. Participants can still mute or "
            "disable camera locally — this is the session default."
        ),
    )


class MintInviteRequest(BaseModel):
    """Body for ``POST /api/v1/call/session/{slug}/invite``."""

    secret: str = Field(min_length=1, max_length=256)


class CloseSessionRequest(BaseModel):
    """Body for ``DELETE /api/v1/call/session/{slug}``."""

    secret: str = Field(min_length=1, max_length=256)


# ── Responses ──


class CreateCallSessionResponse(BaseModel):
    short_slug: str
    long_slug: str
    secret: str
    invite_template: str
    expires_at: str


class MintInviteResponse(BaseModel):
    invite_token: str
    invite_url: str


class CallSessionPublicView(BaseModel):
    """Unauthenticated read for the participant landing page.

    Omits secrets and invite tokens — only the metadata needed to render
    the "join" screen.
    """

    short_slug: str
    title: str | None
    max_participants: int
    mode: str
    started_at: str | None
    host_connected: bool
