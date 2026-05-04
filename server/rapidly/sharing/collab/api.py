"""HTTP endpoints for the Collab chamber (``/api/v1/collab/*``).

Feature-flagged by ``FILE_SHARING_COLLAB_ENABLED``.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from rapidly.config import settings
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from . import actions as collab_service
from .types import (
    CloseSessionRequest,
    CollabSessionPublicView,
    CreateCollabSessionRequest,
    CreateCollabSessionResponse,
    MintInviteRequest,
    MintInviteResponse,
)

router = APIRouter(prefix="/v1/collab", tags=["collab", APITag.private])


SessionNotFound = {
    "description": "Collab session not found or expired.",
    "model": ResourceNotFound.schema(),
}

FeatureDisabled = {
    "description": "The Collab chamber is not enabled on this deployment.",
    "model": ResourceNotFound.schema(),
}


def _require_enabled() -> None:
    if not settings.FILE_SHARING_COLLAB_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post(
    "/session",
    summary="Create Collab Session",
    response_model=CreateCollabSessionResponse,
    responses={404: FeatureDisabled},
)
async def create_session(
    body: CreateCollabSessionRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> CreateCollabSessionResponse:
    channel, raw_secret = await collab_service.create_collab_session(
        redis,
        title=body.title,
        max_participants=body.max_participants,
        kind=body.kind,
    )
    return CreateCollabSessionResponse(
        short_slug=channel.short_slug,
        long_slug=channel.long_slug,
        secret=raw_secret,
        invite_template=f"/collab/{channel.short_slug}?t={{token}}",
        expires_at=collab_service.session_expires_at(),
    )


@router.post(
    "/session/{slug}/invite",
    summary="Mint Collab Guest Invite",
    response_model=MintInviteResponse,
    responses={404: SessionNotFound, 403: FeatureDisabled},
)
async def mint_invite(
    slug: str,
    body: MintInviteRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> MintInviteResponse:
    token = await collab_service.mint_invite_token(redis, slug, body.secret)
    if token is None:
        raise ResourceNotFound()
    return MintInviteResponse(
        invite_token=token,
        invite_url=f"/collab/{slug}?t={token}",
    )


@router.get(
    "/session/{slug}",
    summary="Get Collab Session (public)",
    response_model=CollabSessionPublicView,
    responses={404: SessionNotFound},
)
async def get_session(
    slug: str,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> CollabSessionPublicView:
    view = await collab_service.get_public_view(redis, slug)
    if view is None:
        raise ResourceNotFound()
    return CollabSessionPublicView(**view)  # type: ignore[arg-type]


@router.delete(
    "/session/{slug}",
    summary="Close Collab Session",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: SessionNotFound, 403: FeatureDisabled},
)
async def close_session(
    slug: str,
    body: CloseSessionRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> None:
    ok = await collab_service.close_collab_session(redis, slug, body.secret)
    if not ok:
        raise ResourceNotFound()
