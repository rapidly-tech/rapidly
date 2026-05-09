"""Storefront HTTP routes: public share listing for workspace profiles.

Exposes unauthenticated endpoints for browsing an workspace's
public share catalogue by slug.
"""

from fastapi import Depends

from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from . import actions as storefront_service
from .types import Storefront

router = APIRouter(prefix="/storefronts", tags=["storefronts", APITag.private])

WorkspaceNotFound = {
    "description": "Workspace not found.",
    "model": ResourceNotFound.schema(),
}


@router.get(
    "/{slug}",
    summary="Get Workspace Storefront",
    response_model=Storefront,
    responses={404: WorkspaceNotFound},
)
async def get(
    slug: str,
    session: AsyncReadSession = Depends(get_db_read_session),
    redis: Redis = Depends(get_redis),
) -> Storefront:
    """Get an workspace storefront by slug."""
    storefront = await storefront_service.get_storefront(session, slug, redis=redis)
    if storefront is None:
        raise ResourceNotFound()
    return storefront
