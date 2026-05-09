"""Customer portal routes for workspace details."""

from typing import Annotated

from fastapi import Depends, Path

from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

from ..actions.workspace import (
    customer_workspace as customer_workspace_service,
)
from ..types.workspace import CustomerWorkspaceData

router = APIRouter(prefix="/workspaces", tags=["workspaces", APITag.public])

WorkspaceSlug = Annotated[str, Path(description="The workspace slug.")]
WorkspaceNotFound = {
    "description": "Workspace not found.",
    "model": ResourceNotFound.schema(),
}


@router.get(
    "/{slug}",
    summary="Get Workspace",
    response_model=CustomerWorkspaceData,
    responses={404: WorkspaceNotFound},
)
async def get_workspace(
    slug: WorkspaceSlug,
    session: AsyncSession = Depends(get_db_session),
) -> CustomerWorkspaceData:
    """Get a customer portal's workspace by slug."""
    workspace = await customer_workspace_service.get_by_slug(session, slug)

    if workspace is None:
        raise ResourceNotFound()

    return CustomerWorkspaceData.model_validate(
        {"workspace": workspace, "shares": workspace.shares}
    )
