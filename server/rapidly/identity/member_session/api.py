"""API routes for member session CRUD operations."""

from fastapi import Depends

from rapidly.models import MemberSession
from rapidly.openapi import APITag
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

from . import permissions as auth
from .actions import member_session as member_session_service
from .types import MemberSession as MemberSessionSchema
from .types import MemberSessionCreate

router = APIRouter(
    prefix="/member-sessions",
    tags=["member-sessions", APITag.public],
)


@router.post(
    "/",
    response_model=MemberSessionSchema,
    status_code=201,
    summary="Create Member Session",
    responses={201: {"description": "Member session created."}},
)
async def create(
    member_session_create: MemberSessionCreate,
    auth_subject: auth.MemberSessionWrite,
    session: AsyncSession = Depends(get_db_session),
) -> MemberSession:
    """
    Create a member session.

    This endpoint is only available for workspaces with `member_model_enabled`
    and `seat_based_pricing_enabled` feature flags enabled.
    """
    return await member_session_service.create(
        session, auth_subject, member_session_create
    )
