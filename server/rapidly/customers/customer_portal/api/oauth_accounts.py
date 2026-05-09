"""Customer-portal OAuth account linking routes.

Handles the OAuth2 callback flow for linking third-party accounts
(Microsoft, Discord) to a customer's portal profile, including token
exchange, profile retrieval, and account association.
"""

import uuid
from typing import Any

import httpx
from fastapi import Depends, Query, Request
from fastapi.responses import RedirectResponse
from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2
from httpx_oauth.oauth2 import BaseOAuth2
from pydantic import UUID4

from rapidly.config import settings
from rapidly.core import jwt
from rapidly.core.http import ReturnTo, add_query_parameters, get_safe_return_url
from rapidly.customers.customer.queries import CustomerRepository
from rapidly.customers.customer_session.actions import (
    customer_session as customer_session_service,
)
from rapidly.errors import NotPermitted as Forbidden
from rapidly.errors import RapidlyError
from rapidly.identity.auth.models import (
    Customer,
    Member,
    is_anonymous_principal,
    is_customer_principal,
    is_member_principal,
)
from rapidly.identity.member.queries import MemberRepository
from rapidly.identity.member_session.actions import (
    member_session as member_session_service,
)
from rapidly.integrations.discord.oauth import user_client as discord_user_client
from rapidly.models.customer import CustomerOAuthPlatform
from rapidly.openapi import APITag
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

from .. import permissions as auth
from ..types.oauth_accounts import AuthorizeResponse

router = APIRouter(prefix="/oauth-accounts", tags=["oauth-accounts", APITag.private])


# ---------------------------------------------------------------------------
# OAuth client registry
# ---------------------------------------------------------------------------

OAUTH_CLIENTS: dict[CustomerOAuthPlatform, BaseOAuth2[Any]] = {
    CustomerOAuthPlatform.microsoft: MicrosoftGraphOAuth2(
        settings.MICROSOFT_CLIENT_ID,
        settings.MICROSOFT_CLIENT_SECRET,
        tenant=settings.MICROSOFT_TENANT,
    ),
    CustomerOAuthPlatform.discord: discord_user_client,
}

_RATE_LIMIT_HEADERS = (
    "Retry-After",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "X-RateLimit-Reset-After",
    "X-RateLimit-Bucket",
    "X-RateLimit-Global",
    "X-RateLimit-Scope",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class OAuthCallbackError(RapidlyError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 400)


def _extract_response_attrs(
    response: httpx.Response | None,
) -> dict[str, str | int]:
    if response is None:
        return {}
    attrs: dict[str, str | int] = {"response_status": response.status_code}
    if response.status_code == 429:
        for hdr in _RATE_LIMIT_HEADERS:
            val = response.headers.get(hdr)
            if val is not None:
                attrs[hdr] = val
    return attrs


async def _resolve_customer_and_member(
    auth_subject: Any,
    customer_id: uuid.UUID,
    member_id_str: str | None,
    session: AsyncSession,
) -> tuple[Customer | None, Member | None]:
    """Resolve customer and member from auth subject and state."""
    customer_repo = CustomerRepository.from_session(session)
    member: Member | None = None
    customer: Customer | None = None

    if member_id_str:
        member_repo = MemberRepository.from_session(session)
        member = await member_repo.get_by_id(uuid.UUID(member_id_str))

    if is_member_principal(auth_subject):
        member = auth_subject.subject
        customer = await customer_repo.get_by_id(member.customer_id)
    elif is_customer_principal(auth_subject):
        customer = auth_subject.subject
    elif is_anonymous_principal(auth_subject):
        customer = await customer_repo.get_by_id(customer_id)

    return customer, member


async def _create_session_for_anonymous(
    session: AsyncSession,
    customer: Customer,
    member: Member | None,
    redirect_url: str,
) -> str:
    """Create a session token and add it to the redirect URL."""
    if member is not None:
        token, _ = await member_session_service.create_member_session(session, member)
        return add_query_parameters(redirect_url, member_session_token=token)
    else:
        token, _ = await customer_session_service.create_customer_session(
            session, customer
        )
        return add_query_parameters(redirect_url, customer_session_token=token)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/authorize", name="customer_portal.oauth_accounts.authorize")
async def authorize(
    request: Request,
    return_to: ReturnTo,
    auth_subject: auth.CustomerPortalOAuthAccount,
    platform: CustomerOAuthPlatform = Query(...),
    customer_id: UUID4 = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> AuthorizeResponse:
    state: dict[str, str] = {
        "platform": platform,
        "return_to": return_to,
    }

    if is_member_principal(auth_subject):
        m = auth_subject.subject
        state["customer_id"] = str(m.customer_id)
        state["member_id"] = str(m.id)
    elif is_customer_principal(auth_subject):
        state["customer_id"] = str(auth_subject.subject.id)
    else:
        state["customer_id"] = str(customer_id)

    encoded_state = jwt.encode(
        data=state, secret=settings.SECRET, type="customer_oauth"
    )
    oauth_client = OAUTH_CLIENTS[platform]
    authorization_url = await oauth_client.get_authorization_url(
        redirect_uri=str(request.url_for("customer_portal.oauth_accounts.callback")),
        state=encoded_state,
    )

    return AuthorizeResponse(url=authorization_url)


@router.get("/callback", name="customer_portal.oauth_accounts.callback")
async def callback(
    request: Request,
    auth_subject: auth.CustomerPortalOAuthAccount,
    state: str,
    code: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    try:
        state_data = jwt.decode(
            token=state,
            secret=settings.SECRET,
            type="customer_oauth",
        )
    except jwt.DecodeError as exc:
        raise Forbidden("Invalid state") from exc

    cust_id = uuid.UUID(state_data.get("customer_id"))
    member_id_str = state_data.get("member_id")

    customer, member = await _resolve_customer_and_member(
        auth_subject, cust_id, member_id_str, session
    )

    if customer is None:
        raise Forbidden("Invalid customer")

    return_to = state_data["return_to"]
    platform = CustomerOAuthPlatform(state_data["platform"])
    redirect_url = get_safe_return_url(return_to)

    # Create session for anonymous users
    if is_anonymous_principal(auth_subject):
        redirect_url = await _create_session_for_anonymous(
            session, customer, member, redirect_url
        )

    if code is None or error is not None:
        redirect_url = add_query_parameters(
            redirect_url,
            error=error or "Failed to authorize.",
            error_platform=platform.value,
        )
        return RedirectResponse(redirect_url, 303)

    # Exchange token, fetch profile, and link account
    from ..actions.oauth_accounts import exchange_and_link_oauth_account

    oauth_client = OAUTH_CLIENTS[platform]
    err_msg, err_params = await exchange_and_link_oauth_account(
        session=session,
        oauth_client=oauth_client,
        platform=platform,
        code=code,
        redirect_uri=str(request.url_for("customer_portal.oauth_accounts.callback")),
        customer=customer,
        member=member,
    )

    if err_msg is not None:
        redirect_url = add_query_parameters(redirect_url, **err_params)
        return RedirectResponse(redirect_url, 303)

    return RedirectResponse(redirect_url)
