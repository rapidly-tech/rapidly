"""Pydantic request/response models for the Collab chamber API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Request bodies ──


class CreateCollabSessionRequest(BaseModel):
    """Body for ``POST /api/v1/collab/session``."""

    title: str | None = Field(
        default=None,
        max_length=120,
        description="Human-readable label shown to other participants on join.",
    )
    max_participants: int = Field(
        default=8,
        ge=2,
        le=8,
        description=(
            "Upper bound of concurrent participants (including the host). "
            "v1 caps at 8 — Yjs bandwidth is cheap (~30–200 B/update) but "
            "mesh connections scale with N²."
        ),
    )
    kind: Literal["text", "canvas"] = Field(
        default="text",
        description=(
            "``text`` → plain-text textarea backed by Y.Text. "
            "``canvas`` → whiteboard backed by Y.Array of stroke objects. "
            "v1 ships ``text``; canvas is PR 19 (optional)."
        ),
    )


class MintInviteRequest(BaseModel):
    """Body for ``POST /api/v1/collab/session/{slug}/invite``."""

    secret: str = Field(min_length=1, max_length=256)


class CloseSessionRequest(BaseModel):
    """Body for ``DELETE /api/v1/collab/session/{slug}``."""

    secret: str = Field(min_length=1, max_length=256)


# ── Responses ──


class CreateCollabSessionResponse(BaseModel):
    short_slug: str
    long_slug: str
    secret: str
    invite_template: str
    expires_at: str


class MintInviteResponse(BaseModel):
    invite_token: str
    invite_url: str


class CollabSessionPublicView(BaseModel):
    """Unauthenticated read for the participant landing page.

    Omits secrets and invite tokens — only the metadata needed to render
    the "join" screen.
    """

    short_slug: str
    title: str | None
    max_participants: int
    kind: str
    started_at: str | None
    host_connected: bool
