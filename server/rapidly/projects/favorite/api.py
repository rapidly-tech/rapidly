"""User favorite HTTP routes: list, get, create, delete."""

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import ResourceNotFound
from rapidly.models import UserFavoriteEntityType
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.favorite import actions as favorite_actions
from rapidly.projects.favorite import ordering
from rapidly.projects.favorite import permissions as auth
from rapidly.projects.favorite import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(prefix="/user-favorites", tags=["user-favorites", APITag.public])


@router.get(
    "/",
    summary="List User Favorites",
    response_model=PaginatedList[schemas.UserFavorite],
)
async def list(
    auth_subject: auth.UserFavoritesRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.UserFavoritesSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    entity_type: UserFavoriteEntityType | None = Query(
        None, description="Filter by entity type."
    ),
) -> PaginatedList[schemas.UserFavorite]:
    results, count = await favorite_actions.list(
        session,
        auth_subject,
        entity_type=entity_type,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.UserFavorite.model_validate(favorite) for favorite in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get User Favorite",
    response_model=schemas.UserFavorite,
    responses={404: {}},
)
async def get(
    id: schemas.UserFavoriteID,
    auth_subject: auth.UserFavoritesRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.UserFavorite:
    favorite = await favorite_actions.get(session, auth_subject, id)
    if favorite is None:
        raise ResourceNotFound()
    return schemas.UserFavorite.model_validate(favorite)


@router.post(
    "/",
    summary="Create User Favorite",
    response_model=schemas.UserFavorite,
    status_code=201,
    responses={404: {}, 409: {}},
)
async def create(
    body: schemas.UserFavoriteCreate,
    auth_subject: auth.UserFavoritesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.UserFavorite:
    favorite = await favorite_actions.create(session, auth_subject, body)
    return schemas.UserFavorite.model_validate(favorite)


@router.delete(
    "/{id}",
    summary="Delete User Favorite",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.UserFavoriteID,
    auth_subject: auth.UserFavoritesWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    favorite = await favorite_actions.get(session, auth_subject, id)
    if favorite is None:
        raise ResourceNotFound()
    await favorite_actions.delete(session, auth_subject, favorite)
