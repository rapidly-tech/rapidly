"""Customer-session creation endpoint.

Exposes a single POST route for creating authenticated customer
sessions, with automatic member-session creation for workspaces
that have the member model enabled.
"""

from fastapi import Depends

from rapidly.models import CustomerSession, MemberSession
from rapidly.openapi import APITag
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

from . import permissions as auth
from .actions import customer_session as customer_session_service
from .types import CustomerSession as CustomerSessionSchema
from .types import CustomerSessionCreate

router = APIRouter(
    prefix="/customer-sessions",
    tags=["customer-sessions", APITag.public],
)


@router.post(
    "/",
    response_model=CustomerSessionSchema,
    status_code=201,
    summary="Create Customer Session",
    responses={201: {"description": "Customer session created."}},
)
async def create(
    customer_session_create: CustomerSessionCreate,
    auth_subject: auth.CustomerSessionWrite,
    session: AsyncSession = Depends(get_db_session),
) -> CustomerSession | MemberSession:
    """
    Create a customer session.

    For workspaces with `member_model_enabled`, this will automatically
    create a member session for the owner member of the customer.
    """
    return await customer_session_service.create(
        session, auth_subject, customer_session_create
    )
