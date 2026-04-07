"""Cross-entity search endpoint for the dashboard.

Provides a single search route that queries across products, customers,
and other entities within a workspace.
"""

from fastapi import Depends, Query
from pydantic import UUID4

from rapidly.openapi import APITag
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.routing import APIRouter

from . import actions as search_service
from . import permissions as auth
from .types import SearchResults

router = APIRouter(tags=["search", APITag.private])


@router.get("/search", response_model=SearchResults)
async def search(
    auth_subject: auth.SearchRead,
    workspace_id: UUID4 = Query(..., description="Workspace ID to search within"),
    query: str = Query(..., description="Search query string"),
    limit: int = Query(20, ge=1, le=50, description="Maximum number of results"),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> SearchResults:
    """Internal search endpoint for dashboard."""
    hits = await search_service.search(
        session,
        auth_subject,
        workspace_id=workspace_id,
        query=query,
        limit=limit,
    )

    return SearchResults(results=hits)
