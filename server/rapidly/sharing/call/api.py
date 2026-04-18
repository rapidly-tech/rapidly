"""HTTP endpoints for the Call chamber (``/api/v1/call/*``).

Feature-flagged by ``FILE_SHARING_CALL_ENABLED``.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from rapidly.config import settings
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from . import actions as call_service
from .types import (
    CallSessionPublicView,
    CloseSessionRequest,
    CreateCallSessionRequest,
    CreateCallSessionResponse,
    MintInviteRequest,
    MintInviteResponse,
)

router = APIRouter(prefix="/v1/call", tags=["call", APITag.private])


SessionNotFound = {
    "description": "Call session not found or expired.",
    "model": ResourceNotFound.schema(),
}

FeatureDisabled = {
    "description": "The Call chamber is not enabled on this deployment.",
    "model": ResourceNotFound.schema(),
}


def _require_enabled() -> None:
    if not settings.FILE_SHARING_CALL_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post(
    "/session",
    summary="Create Call Session",
    response_model=CreateCallSessionResponse,
    responses={404: FeatureDisabled},
)
async def create_session(
    body: CreateCallSessionRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> CreateCallSessionResponse:
    channel, raw_secret = await call_service.create_call_session(
        redis,
        title=body.title,
        max_participants=body.max_participants,
        mode=body.mode,
    )
    return CreateCallSessionResponse(
        short_slug=channel.short_slug,
        long_slug=channel.long_slug,
        secret=raw_secret,
        invite_template=f"/call/{channel.short_slug}?t={{token}}",
        expires_at=call_service.session_expires_at(),
    )


@router.post(
    "/session/{slug}/invite",
    summary="Mint Call Guest Invite",
    response_model=MintInviteResponse,
    responses={404: SessionNotFound, 403: FeatureDisabled},
)
async def mint_invite(
    slug: str,
    body: MintInviteRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> MintInviteResponse:
    token = await call_service.mint_invite_token(redis, slug, body.secret)
    if token is None:
        raise ResourceNotFound()
    return MintInviteResponse(
        invite_token=token,
        invite_url=f"/call/{slug}?t={token}",
    )


@router.get(
    "/session/{slug}",
    summary="Get Call Session (public)",
    response_model=CallSessionPublicView,
    responses={404: SessionNotFound},
)
async def get_session(
    slug: str,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> CallSessionPublicView:
    view = await call_service.get_public_view(redis, slug)
    if view is None:
        raise ResourceNotFound()
    return CallSessionPublicView(**view)  # type: ignore[arg-type]


@router.delete(
    "/session/{slug}",
    summary="Close Call Session",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: SessionNotFound, 403: FeatureDisabled},
)
async def close_session(
    slug: str,
    body: CloseSessionRequest,
    _: None = Depends(_require_enabled),
    redis: Redis = Depends(get_redis),
) -> None:
    ok = await call_service.close_call_session(redis, slug, body.secret)
    if not ok:
        raise ResourceNotFound()
