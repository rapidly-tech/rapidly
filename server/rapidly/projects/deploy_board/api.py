"""HTTP routes for project deploy-board configuration."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.deploy_board import actions as board_actions
from rapidly.projects.deploy_board import permissions as auth
from rapidly.projects.deploy_board import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/project-deploy-boards",
    tags=["project-deploy-boards", APITag.public],
)


@router.get(
    "/",
    summary="List Project Deploy Boards",
    response_model=PaginatedList[schemas.ProjectDeployBoard],
)
async def list(
    auth_subject: auth.DeployBoardsRead,
    pagination: PaginationParamsQuery,
    session: AsyncReadSession = Depends(get_db_read_session),
    project_id: UUID | None = Query(None, description="Filter by project ID."),
) -> PaginatedList[schemas.ProjectDeployBoard]:
    results, count = await board_actions.list_boards(
        session,
        auth_subject,
        project_id=project_id,
        pagination=pagination,
    )
    return PaginatedList.from_paginated_results(
        [schemas.ProjectDeployBoard.model_validate(b) for b in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Project Deploy Board",
    response_model=schemas.ProjectDeployBoard,
    responses={404: {}},
)
async def get(
    id: schemas.ProjectDeployBoardID,
    auth_subject: auth.DeployBoardsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.ProjectDeployBoard:
    board = await board_actions.get(session, auth_subject, id)
    if board is None:
        raise ResourceNotFound()
    return schemas.ProjectDeployBoard.model_validate(board)


@router.post(
    "/",
    summary="Create Project Deploy Board",
    response_model=schemas.ProjectDeployBoardWithToken,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.ProjectDeployBoardCreate,
    auth_subject: auth.DeployBoardsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectDeployBoardWithToken:
    """Returns the token *once* on create — clients should store it.

    Subsequent reads via ``GET`` do not surface the token; rotate
    via ``POST /{id}/token`` if you lose it.
    """
    board = await board_actions.create(session, auth_subject, body)
    return schemas.ProjectDeployBoardWithToken.model_validate(board)


@router.patch(
    "/{id}",
    summary="Update Project Deploy Board",
    response_model=schemas.ProjectDeployBoard,
    responses={400: {}, 404: {}},
)
async def update(
    id: schemas.ProjectDeployBoardID,
    body: schemas.ProjectDeployBoardUpdate,
    auth_subject: auth.DeployBoardsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectDeployBoard:
    board = await board_actions.get(session, auth_subject, id)
    if board is None:
        raise ResourceNotFound()
    updated = await board_actions.update(session, auth_subject, board, body)
    return schemas.ProjectDeployBoard.model_validate(updated)


@router.post(
    "/{id}/token",
    summary="Rotate Public Token",
    response_model=schemas.ProjectDeployBoardWithToken,
    responses={404: {}},
)
async def rotate_token(
    id: schemas.ProjectDeployBoardID,
    auth_subject: auth.DeployBoardsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.ProjectDeployBoardWithToken:
    """Replace the public token, invalidating every URL holder.

    Returns the new token *once* — there's no other way to retrieve it
    later, by design.
    """
    board = await board_actions.get(session, auth_subject, id)
    if board is None:
        raise ResourceNotFound()
    rotated = await board_actions.rotate_token(session, auth_subject, board)
    return schemas.ProjectDeployBoardWithToken.model_validate(rotated)


@router.delete(
    "/{id}",
    summary="Delete Project Deploy Board",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.ProjectDeployBoardID,
    auth_subject: auth.DeployBoardsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    board = await board_actions.get(session, auth_subject, id)
    if board is None:
        raise ResourceNotFound()
    await board_actions.delete(session, auth_subject, board)
