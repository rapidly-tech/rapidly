"""HTTP endpoints for the Watch chamber (``/api/v1/watch/*``).

Feature-flagged by ``FILE_SHARING_WATCH_ENABLED`` — endpoints 404 when
off so the surface stays invisible on unenabled deployments.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from rapidly.config import settings
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from . import actions as watch_service
from .types import (
    CloseSessionRequest,
    CreateWatchSessionRequest,
    CreateWatchSessionResponse,
    MintInviteRequest,
    MintInviteResponse,
    WatchSessionPublicView,
)

router = APIRouter(prefix="/v1/watch", tags=["watch", APITag.private])


SessionNotFound = {
    "description": "Watch session not found or expired.",
    "model": ResourceNotFound.schema(),
}

FeatureDisabled = {
    "description": "The Watch chamber is not enabled on this deployment.",
    "model": ResourceNotFound.schema(),
}


def _require_enabled() -> None:
    if not settings.FILE_SHARING_WATCH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post(
    "/session",
    summary="Create Watch Session",
    response_model=CreateWatchSessionResponse,
    responses={404: FeatureDisabled},
)
async def create_session(
    body: CreateWatchSessionRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> CreateWatchSessionResponse:
    channel, raw_secret = await watch_service.create_watch_session(
        redis,
        title=body.title,
        max_viewers=body.max_viewers,
        source_url=str(body.source_url) if body.source_url else None,
        source_kind=body.source_kind,
    )
    return CreateWatchSessionResponse(
        short_slug=channel.short_slug,
        long_slug=channel.long_slug,
        secret=raw_secret,
        invite_template=f"/watch/{channel.short_slug}?t={{token}}",
        expires_at=watch_service.session_expires_at(),
    )


@router.post(
    "/session/{slug}/invite",
    summary="Mint Watch Guest Invite",
    response_model=MintInviteResponse,
    responses={404: SessionNotFound, 403: FeatureDisabled},
)
async def mint_invite(
    slug: str,
    body: MintInviteRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> MintInviteResponse:
    token = await watch_service.mint_invite_token(redis, slug, body.secret)
    if token is None:
        raise ResourceNotFound()
    return MintInviteResponse(
        invite_token=token,
        invite_url=f"/watch/{slug}?t={token}",
    )


@router.get(
    "/session/{slug}",
    summary="Get Watch Session (public)",
    response_model=WatchSessionPublicView,
    responses={404: SessionNotFound},
)
async def get_session(
    slug: str,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> WatchSessionPublicView:
    view = await watch_service.get_public_view(redis, slug)
    if view is None:
        raise ResourceNotFound()
    return WatchSessionPublicView(**view)  # type: ignore[arg-type]


@router.delete(
    "/session/{slug}",
    summary="Close Watch Session",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: SessionNotFound, 403: FeatureDisabled},
)
async def close_session(
    slug: str,
    body: CloseSessionRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> None:
    ok = await watch_service.close_watch_session(redis, slug, body.secret)
    if not ok:
        raise ResourceNotFound()
