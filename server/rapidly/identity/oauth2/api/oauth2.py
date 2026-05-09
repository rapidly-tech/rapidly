"""OAuth2 / OIDC HTTP endpoints.

Routes for authorization, token exchange, dynamic client registration,
token revocation, token introspection, and the OIDC UserInfo endpoint.
Also includes a private endpoint for listing a user's registered clients.
"""

from collections.abc import Sequence
from typing import Literal, cast

from fastapi import Depends, Form, HTTPException, Request, Response
from fastapi.openapi.constants import REF_TEMPLATE

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.identity.auth.dependencies import (
    WebUserOrAnonymous,
    WebUserRead,
    WebUserWrite,
)
from rapidly.identity.auth.models import is_user_principal
from rapidly.models import OAuth2Token, Workspace
from rapidly.openapi import APITag
from rapidly.platform.workspace.queries import WorkspaceRepository
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

from ..actions.oauth2_client import oauth2_client as oauth2_client_service
from ..authorization_server import (
    AuthorizationServer,
    ClientConfigurationEndpoint,
    ClientRegistrationEndpoint,
    IntrospectionEndpoint,
    RevocationEndpoint,
)
from ..dependencies import get_authorization_server, get_token
from ..grants import AuthorizationCodeGrant
from ..sub_type import SubType
from ..types import (
    AuthorizeResponse,
    IntrospectTokenResponse,
    OAuth2Client,
    OAuth2ClientConfiguration,
    OAuth2ClientConfigurationUpdate,
    RevokeTokenResponse,
    TokenResponse,
    authorize_response_adapter,
)
from ..types import UserInfo as UserInfoSchema
from ..userinfo import UserInfo, generate_user_info

router = APIRouter(prefix="/oauth2", tags=["oauth2"])


# ---------------------------------------------------------------------------
# Client management
# ---------------------------------------------------------------------------


def _extract_user(auth_subject: WebUserOrAnonymous) -> object | None:
    """Return the User if authenticated, else None (for anonymous callers)."""
    return auth_subject.subject if is_user_principal(auth_subject) else None


@router.get(
    "/",
    summary="List Clients",
    tags=["clients", APITag.private],
    response_model=PaginatedList[OAuth2Client],
)
async def list(
    auth_subject: WebUserRead,
    pagination: PaginationParamsQuery,
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedList[OAuth2Client]:
    """List OAuth2 clients belonging to the authenticated user."""
    results, count = await oauth2_client_service.list(
        session, auth_subject, pagination=pagination
    )
    return PaginatedList.from_paginated_results(
        [OAuth2Client.model_validate(r) for r in results], count, pagination
    )


@router.post(
    "/register",
    summary="Create Client",
    tags=["clients", APITag.public],
    name="oauth2:create_client",
)
async def create(
    client_configuration: OAuth2ClientConfiguration,
    request: Request,
    auth_subject: WebUserOrAnonymous,
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
) -> Response:
    """Register a new OAuth2 client (RFC 7591)."""
    request.state.user = _extract_user(auth_subject)
    request.state.parsed_data = client_configuration.model_dump(
        mode="json", exclude_none=True
    )
    return authorization_server.create_endpoint_response(
        ClientRegistrationEndpoint.ENDPOINT_NAME, request
    )


@router.get(
    "/register/{client_id}",
    tags=["clients", APITag.public],
    summary="Get Client",
    name="oauth2:get_client",
)
async def get(
    client_id: str,
    request: Request,
    auth_subject: WebUserOrAnonymous,
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
) -> Response:
    """Read an OAuth2 client's configuration (RFC 7592)."""
    request.state.user = _extract_user(auth_subject)
    return authorization_server.create_endpoint_response(
        ClientConfigurationEndpoint.ENDPOINT_NAME, request
    )


@router.put(
    "/register/{client_id}",
    tags=["clients", APITag.public],
    summary="Update Client",
    name="oauth2:update_client",
)
async def update(
    client_id: str,
    client_configuration: OAuth2ClientConfigurationUpdate,
    request: Request,
    auth_subject: WebUserOrAnonymous,
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
) -> Response:
    """Update an OAuth2 client's configuration (RFC 7592)."""
    request.state.user = _extract_user(auth_subject)
    request.state.parsed_data = client_configuration.model_dump(
        mode="json", exclude_none=True
    )
    return authorization_server.create_endpoint_response(
        ClientConfigurationEndpoint.ENDPOINT_NAME, request
    )


@router.delete(
    "/register/{client_id}",
    tags=["clients", APITag.public],
    summary="Delete Client",
    name="oauth2:delete_client",
)
async def delete(
    client_id: str,
    request: Request,
    auth_subject: WebUserOrAnonymous,
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
) -> Response:
    """Soft-delete an OAuth2 client (RFC 7592)."""
    request.state.user = _extract_user(auth_subject)
    return authorization_server.create_endpoint_response(
        ClientConfigurationEndpoint.ENDPOINT_NAME, request
    )


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


@router.get("/authorize", tags=[APITag.public])
async def authorize(
    request: Request,
    auth_subject: WebUserOrAnonymous,
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
    session: AsyncSession = Depends(get_db_session),
) -> AuthorizeResponse:
    """Begin the authorization code flow (returns consent metadata or auto-approves)."""
    user = auth_subject.subject if is_user_principal(auth_subject) else None
    await request.form()
    grant: AuthorizationCodeGrant = authorization_server.get_consent_grant(
        request=request, end_user=user
    )

    if grant.prompt == "login":
        raise HTTPException(status_code=401)

    if grant.prompt == "none":
        return authorization_server.create_authorization_response(
            request=request, grant_user=user, save_consent=False
        )

    # Fetch workspaces when the grant targets a workspace subject
    available_workspaces: Sequence[Workspace] | None = None
    if grant.sub_type == SubType.workspace:
        assert is_user_principal(auth_subject)
        ws_repo = WorkspaceRepository.from_session(session)
        available_workspaces = await ws_repo.get_all_by_user(auth_subject.subject.id)

    payload = grant.request.payload
    assert payload is not None

    return authorize_response_adapter.validate_python(
        {
            "client": grant.client,
            "scopes": payload.scope,
            "sub_type": grant.sub_type,
            "sub": grant.sub,
            "workspaces": available_workspaces,
        }
    )


@router.post("/consent", tags=[APITag.private])
async def consent(
    request: Request,
    auth_subject: WebUserWrite,
    action: Literal["allow", "deny"] = Form(...),
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
) -> Response:
    """Handle the user's consent decision (allow or deny)."""
    await request.form()
    approved_user = auth_subject.subject if action == "allow" else None
    return authorization_server.create_authorization_response(
        request=request, grant_user=approved_user, save_consent=True
    )


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


@router.post(
    "/token",
    summary="Request Token",
    name="oauth2:request_token",
    operation_id="oauth2:request_token",
    tags=[APITag.public],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "oneOf": [
                            {
                                "$ref": REF_TEMPLATE.format(
                                    model="AuthorizationCodeTokenRequest"
                                )
                            },
                            {"$ref": REF_TEMPLATE.format(model="RefreshTokenRequest")},
                            {"$ref": REF_TEMPLATE.format(model="WebTokenRequest")},
                        ]
                    }
                }
            },
        },
    },
    response_model=TokenResponse,
)
async def token(
    request: Request,
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
) -> Response:
    """Exchange a grant for an access token."""
    await request.form()
    return authorization_server.create_token_response(request)


# ---------------------------------------------------------------------------
# Revocation (RFC 7009)
# ---------------------------------------------------------------------------


@router.post(
    "/revoke",
    summary="Revoke Token",
    name="oauth2:revoke_token",
    operation_id="oauth2:revoke_token",
    tags=[APITag.public],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {"$ref": REF_TEMPLATE.format(model="RevokeTokenRequest")}
                }
            },
        },
    },
    response_model=RevokeTokenResponse,
)
async def revoke(
    request: Request,
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
) -> Response:
    """Revoke an access or refresh token."""
    await request.form()
    return authorization_server.create_endpoint_response(
        RevocationEndpoint.ENDPOINT_NAME, request
    )


# ---------------------------------------------------------------------------
# Introspection (RFC 7662)
# ---------------------------------------------------------------------------


@router.post(
    "/introspect",
    summary="Introspect Token",
    name="oauth2:introspect_token",
    operation_id="oauth2:introspect_token",
    tags=[APITag.public],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "$ref": REF_TEMPLATE.format(model="IntrospectTokenRequest")
                    }
                }
            },
        },
    },
    response_model=IntrospectTokenResponse,
)
async def introspect(
    request: Request,
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
) -> Response:
    """Return metadata about an active token."""
    await request.form()
    return authorization_server.create_endpoint_response(
        IntrospectionEndpoint.ENDPOINT_NAME, request
    )


# ---------------------------------------------------------------------------
# UserInfo (OIDC)
# ---------------------------------------------------------------------------


@router.get(
    "/userinfo",
    summary="Get User Info",
    name="oauth2:userinfo",
    operation_id="oauth2:userinfo",
    response_model=UserInfoSchema,
    response_model_exclude_unset=True,
    tags=[APITag.public],
)
async def userinfo_get(token: OAuth2Token = Depends(get_token)) -> UserInfo:
    """Return OpenID Connect claims for the authenticated subject."""
    return generate_user_info(token.get_sub_type_value(), cast(str, token.scope))


@router.post(
    "/userinfo",
    summary="Get User Info",
    response_model=UserInfoSchema,
    response_model_exclude_unset=True,
    include_in_schema=False,
)
async def userinfo_post(token: OAuth2Token = Depends(get_token)) -> UserInfo:
    """POST variant of the UserInfo endpoint (not in public OpenAPI schema)."""
    return generate_user_info(token.get_sub_type_value(), cast(str, token.scope))
