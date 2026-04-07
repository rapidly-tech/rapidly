"""Discovery endpoints: JWKS and OpenID Connect provider configuration.

Serves the standard ``.well-known`` URLs that OAuth2 / OIDC clients use
to bootstrap their connection to the authorization server.
"""

from typing import Any

from fastapi import Depends, Request

from rapidly.config import settings
from rapidly.routing import APIRouter

from ..authorization_server import AuthorizationServer
from ..dependencies import get_authorization_server
from ..metadata import get_server_metadata

router = APIRouter(prefix="/.well-known", tags=["well_known"], include_in_schema=False)


@router.get("/jwks.json", name="well_known.jwks")
async def jwks_document() -> dict[str, Any]:
    """Return the JSON Web Key Set (public keys only)."""
    return settings.JWKS.as_dict(is_private=False)


@router.get("/openid-configuration", name="well_known.openid_configuration")
async def openid_configuration(
    request: Request,
    authorization_server: AuthorizationServer = Depends(get_authorization_server),
) -> dict[str, Any]:
    """Return the OpenID Provider metadata document."""

    def resolve_url(name: str) -> str:
        return str(request.url_for(name))

    return get_server_metadata(authorization_server, resolve_url).model_dump(
        exclude_unset=True
    )
