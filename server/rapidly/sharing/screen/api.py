"""HTTP endpoints for the Screen chamber.

Mounted under ``/api/v1/screen/``. Endpoints are gated behind the
``FILE_SHARING_SCREEN_ENABLED`` config flag — when False the router is
registered but every handler returns 404 so the surface stays invisible.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from rapidly.config import settings
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from . import actions as screen_service
from .types import (
    CloseSessionRequest,
    CreateScreenSessionRequest,
    CreateScreenSessionResponse,
    MintInviteRequest,
    MintInviteResponse,
    ScreenSessionPublicView,
)

router = APIRouter(prefix="/v1/screen", tags=["screen", APITag.private])


SessionNotFound = {
    "description": "Screen session not found or expired.",
    "model": ResourceNotFound.schema(),
}

FeatureDisabled = {
    "description": "The Screen chamber is not enabled on this deployment.",
    "model": ResourceNotFound.schema(),
}


def _require_enabled() -> None:
    """Dependency that 404s every endpoint when the feature flag is off.

    Returning 404 (rather than 403) intentionally hides the existence of
    the endpoint from unenabled deployments — same posture we use for
    any chamber-gated surface.
    """
    if not settings.FILE_SHARING_SCREEN_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post(
    "/session",
    summary="Create Screen Session",
    response_model=CreateScreenSessionResponse,
    responses={404: FeatureDisabled},
)
async def create_session(
    body: CreateScreenSessionRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> CreateScreenSessionResponse:
    """Create a new screen-sharing session.

    Anonymous-friendly in v1 — matches the file-sharing anonymous flow.
    Returns the host secret ONCE at creation; clients must persist it
    client-side because it's never stored in plaintext (only its hash).
    """
    channel, raw_secret = await screen_service.create_screen_session(
        redis, title=body.title, max_viewers=body.max_viewers
    )
    invite_template = f"/screen/{channel.short_slug}?t={{token}}"
    # Expires_at is informational: TTL + now. Clients don't rely on exact
    # wall-clock alignment — the signaling server is the source of truth.
    from datetime import UTC, datetime, timedelta

    expires_at = (
        datetime.now(UTC) + timedelta(seconds=screen_service.SCREEN_SESSION_TTL)
    ).isoformat()
    return CreateScreenSessionResponse(
        short_slug=channel.short_slug,
        long_slug=channel.long_slug,
        secret=raw_secret,
        invite_template=invite_template,
        expires_at=expires_at,
    )


@router.post(
    "/session/{slug}/invite",
    summary="Mint Screen Guest Invite",
    response_model=MintInviteResponse,
    responses={404: SessionNotFound, 403: FeatureDisabled},
)
async def mint_invite(
    slug: str,
    body: MintInviteRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> MintInviteResponse:
    """Mint a new invite token for a guest.

    Authorization proof: the host presents the channel secret. Failure
    to match returns 404 (not 403) to avoid distinguishing a wrong
    secret from a non-existent session.
    """
    token = await screen_service.mint_invite_token(redis, slug, body.secret)
    if token is None:
        raise ResourceNotFound()
    return MintInviteResponse(
        invite_token=token,
        invite_url=f"/screen/{slug}?t={token}",
    )


@router.get(
    "/session/{slug}",
    summary="Get Screen Session (public)",
    response_model=ScreenSessionPublicView,
    responses={404: SessionNotFound},
)
async def get_session(
    slug: str,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> ScreenSessionPublicView:
    """Guest-facing view. No secrets, no invites — just the metadata
    needed to render the "join" screen."""
    view = await screen_service.get_public_view(redis, slug)
    if view is None:
        raise ResourceNotFound()
    return ScreenSessionPublicView(**view)  # type: ignore[arg-type]


@router.delete(
    "/session/{slug}",
    summary="Close Screen Session",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: SessionNotFound, 403: FeatureDisabled},
)
async def close_session(
    slug: str,
    body: CloseSessionRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> None:
    """Tear the session down. Requires the host secret."""
    ok = await screen_service.close_screen_session(redis, slug, body.secret)
    if not ok:
        raise ResourceNotFound()
    # 204 — no body.
