"""Customer-portal session routes: OTP request, token exchange, and introspection.

Implements the customer-portal authentication flow: request a one-time
code via email, exchange it for a bearer token, and introspect active
sessions.
"""

import structlog
from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from rapidly.core.db.postgres import AsyncSession
from rapidly.core.rate_limit import check_otp_rate_limit
from rapidly.identity.auth.models import is_customer_principal, is_member_principal
from rapidly.models import CustomerSession, MemberSession
from rapidly.openapi import APITag
from rapidly.postgres import get_db_session
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

from .. import permissions as auth
from ..actions.customer_session import (
    CustomerDoesNotExist,
    CustomerSelectionRequired,
    WorkspaceDoesNotExist,
)
from ..actions.customer_session import customer_session as customer_session_service
from ..types.customer_session import (
    CustomerCustomerSession,
    CustomerSelectionOption,
    CustomerSelectionRequiredResponse,
    CustomerSessionCodeAuthenticateRequest,
    CustomerSessionCodeAuthenticateResponse,
    CustomerSessionCodeInvalidOrExpiredResponse,
    CustomerSessionCodeRequest,
    PortalAuthenticatedUser,
)

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/customer-session", tags=["customer-session"])


# ---------------------------------------------------------------------------
# Authenticated user info
# ---------------------------------------------------------------------------


@router.get(
    "/user",
    summary="Get Authenticated Portal User",
    tags=[APITag.public],
    response_model=PortalAuthenticatedUser,
)
async def get_authenticated_user(
    auth_subject: auth.CustomerPortalUnionRead,
) -> PortalAuthenticatedUser:
    """Return info about the currently authenticated portal user."""
    if is_member_principal(auth_subject):
        m = auth_subject.subject
        return PortalAuthenticatedUser(
            type="member",
            name=m.name,
            email=m.email,
            customer_id=m.customer_id,
            member_id=m.id,
            role=m.role,
        )
    elif is_customer_principal(auth_subject):
        c = auth_subject.subject
        return PortalAuthenticatedUser(
            type="customer",
            name=c.name,
            email=c.email,
            customer_id=c.id,
            role=None,
        )
    raise ValueError("Invalid auth subject type")


# ---------------------------------------------------------------------------
# Session introspection
# ---------------------------------------------------------------------------


@router.get(
    "/introspect",
    summary="Introspect Customer Session",
    tags=[APITag.public],
    response_model=CustomerCustomerSession,
)
async def introspect(
    auth_subject: auth.CustomerPortalUnionRead,
) -> CustomerSession | MemberSession:
    """Introspect the current session and return its information."""
    active_session = auth_subject.session
    assert isinstance(active_session, (CustomerSession, MemberSession))
    return active_session


# ---------------------------------------------------------------------------
# OTP code request
# ---------------------------------------------------------------------------


@router.post(
    "/request",
    name="customer_portal.customer_session.request",
    status_code=202,
    response_model=None,
    tags=[APITag.private],
    responses={
        409: {
            "description": "Multiple customers found for this email.",
            "model": CustomerSelectionRequiredResponse,
        },
    },
)
async def request(
    customer_session_code_request: CustomerSessionCodeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Response | None:
    try:
        code_record, code = await customer_session_service.request(
            session,
            customer_session_code_request.email,
            customer_session_code_request.workspace_id,
            customer_session_code_request.customer_id,
        )
    except CustomerSelectionRequired as exc:
        return JSONResponse(
            status_code=409,
            content=CustomerSelectionRequiredResponse(
                customers=[
                    CustomerSelectionOption(id=c.id, name=c.name) for c in exc.customers
                ],
            ).model_dump(mode="json"),
        )
    except (CustomerDoesNotExist, WorkspaceDoesNotExist):
        # Never reveal whether the customer or workspace actually exists
        return None

    await customer_session_service.send(session, code_record, code)
    return None


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


@router.post(
    "/authenticate",
    name="customer_portal.customer_session.authenticate",
    responses={
        401: CustomerSessionCodeInvalidOrExpiredResponse,
    },
    tags=[APITag.private],
)
async def authenticate(
    authenticated_request: CustomerSessionCodeAuthenticateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> CustomerSessionCodeAuthenticateResponse:
    await check_otp_rate_limit(redis, request, key_prefix="portal")
    token, _ = await customer_session_service.authenticate(
        session, authenticated_request.code
    )
    return CustomerSessionCodeAuthenticateResponse(token=token)
