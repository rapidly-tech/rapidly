"""Pydantic request/response models for the Watch chamber API."""

from __future__ import annotations

from typing import Literal

from pydantic import AnyUrl, BaseModel, Field, field_validator

# ── Request bodies ──


class CreateWatchSessionRequest(BaseModel):
    """Body for ``POST /api/v1/watch/session``."""

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
    source_url: AnyUrl | None = Field(
        default=None,
        description=(
            "HTTP(S) URL of the video the host intends to play. Optional at "
            "session creation — the host can update it once connected. Only "
            "validated for shape here; the browser is the authority for "
            "whether the URL actually resolves."
        ),
    )
    source_kind: Literal["url", "local"] = Field(
        default="url",
        description=(
            "``url`` = host plays a remote URL. ``local`` = host streams a "
            "local file over the DataChannel (PR 12). v1 ships ``url``."
        ),
    )

    @field_validator("source_url")
    @classmethod
    def _scheme_must_be_http(cls, v: AnyUrl | None) -> AnyUrl | None:
        """Defense-in-depth: Pydantic's ``AnyUrl`` accepts any well-formed
        URI including ``javascript:`` and ``data:`` schemes. The client
        already refuses those before assignment to ``<video src>``, but
        the backend should reject them at the API boundary so a
        crafted-URL session can't be persisted and echoed back to
        unsuspecting clients that skip the client-side validator."""
        if v is None:
            return v
        if v.scheme not in ("http", "https"):
            raise ValueError("source_url must use http or https scheme")
        return v


class MintInviteRequest(BaseModel):
    """Body for ``POST /api/v1/watch/session/{slug}/invite``."""

    secret: str = Field(min_length=1, max_length=256)


class CloseSessionRequest(BaseModel):
    """Body for ``DELETE /api/v1/watch/session/{slug}``."""

    secret: str = Field(min_length=1, max_length=256)


# ── Responses ──


class CreateWatchSessionResponse(BaseModel):
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


class WatchSessionPublicView(BaseModel):
    """Unauthenticated read for the guest landing page.

    Deliberately omits secrets, invite tokens, and host identity. Only
    information needed to render the "about to join" screen.
    """

    short_slug: str
    title: str | None
    max_viewers: int
    source_url: str | None
    source_kind: str
    started_at: str | None
    host_connected: bool
