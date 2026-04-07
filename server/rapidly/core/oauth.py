"""OAuth authorization-code flow utilities.

Manages the ephemeral state that lives between the authorization
redirect and the provider callback:

* **Redis** stores the serialised state payload, keyed by a
  cryptographic nonce with a configurable TTL.
* **Cookies** carry the same nonce so the callback can verify that
  the browser session that started the flow is the one finishing it.
"""

from __future__ import annotations

import json
import secrets
from typing import Any, Literal

from fastapi import Request
from fastapi.responses import RedirectResponse
from httpx_oauth.oauth2 import OAuth2Token

from rapidly.config import settings
from rapidly.errors import RedirectionError
from rapidly.redis import Redis

# ---------------------------------------------------------------------------
# Types and constants
# ---------------------------------------------------------------------------

OAuthStateType = Literal["microsoft", "google", "apple"]

_TTL_SECONDS = int(settings.OAUTH_STATE_TTL.total_seconds())
_LOCALHOST_NAMES = frozenset({"127.0.0.1", "localhost"})


class OAuthCallbackError(RedirectionError):
    """Raised when the OAuth callback cannot be completed."""


# ---------------------------------------------------------------------------
# Redis state store
# ---------------------------------------------------------------------------


def _cache_key(provider: OAuthStateType, nonce: str) -> str:
    return f"oauth_state:{provider}:{nonce}"


async def store_oauth_state(
    redis: Redis,
    nonce: str,
    state_data: dict[str, Any],
    type: OAuthStateType,
) -> None:
    """Persist *state_data* in Redis under a nonce-based key."""
    await redis.setex(_cache_key(type, nonce), _TTL_SECONDS, json.dumps(state_data))


async def retrieve_oauth_state(
    redis: Redis, nonce: str, type: OAuthStateType
) -> dict[str, Any]:
    """Load and deserialise the state payload for *nonce*."""
    raw = await redis.get(_cache_key(type, nonce))
    if not raw:
        raise OAuthCallbackError("Invalid state")
    return json.loads(raw)


async def delete_oauth_state(redis: Redis, nonce: str, type: OAuthStateType) -> None:
    """Remove the state entry so it cannot be replayed."""
    await redis.delete(_cache_key(type, nonce))


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def _requires_secure(request: Request) -> bool:
    """True unless the request targets a localhost address."""
    return request.url.hostname not in _LOCALHOST_NAMES


def set_login_cookie(
    request: Request,
    response: RedirectResponse,
    nonce: str,
    *,
    cross_site: bool = False,
) -> None:
    """Write a short-lived cookie carrying the OAuth nonce."""
    response.set_cookie(
        key=settings.OAUTH_STATE_COOKIE_KEY,
        value=nonce,
        max_age=_TTL_SECONDS,
        path="/",
        secure=_requires_secure(request),
        httponly=True,
        samesite="none" if cross_site else "lax",
    )


def clear_login_cookie(
    request: Request,
    response: RedirectResponse,
    *,
    cross_site: bool = False,
) -> None:
    """Expire the OAuth nonce cookie immediately."""
    response.set_cookie(
        key=settings.OAUTH_STATE_COOKIE_KEY,
        value="",
        max_age=0,
        path="/",
        secure=_requires_secure(request),
        httponly=True,
        samesite="none" if cross_site else "lax",
    )


# ---------------------------------------------------------------------------
# High-level flow helpers
# ---------------------------------------------------------------------------


async def create_authorization_response(
    request: Request,
    redis: Redis,
    state: dict[str, Any],
    callback_route: str,
    oauth_client: Any,
    scopes: list[str],
    *,
    type: OAuthStateType,
) -> RedirectResponse:
    """Build the redirect that sends the user to the OAuth provider.

    Generates a nonce, persists the state in Redis, obtains the
    authorization URL from *oauth_client*, and sets the nonce cookie.
    """
    nonce = secrets.token_urlsafe()
    await store_oauth_state(redis, nonce, {**state, "nonce": nonce}, type=type)

    auth_url = await oauth_client.get_authorization_url(
        redirect_uri=str(request.url_for(callback_route)),
        state=nonce,
        scope=scopes,
    )

    response = RedirectResponse(auth_url, 303)
    set_login_cookie(request, response, nonce)
    return response


async def validate_callback(
    request: Request,
    redis: Redis,
    token_data: OAuth2Token,
    state: str | None,
    *,
    type: OAuthStateType,
) -> dict[str, Any]:
    """Verify an incoming OAuth callback and return the stored state.

    Checks for provider-side errors, validates that the ``state`` query
    parameter matches the nonce cookie, loads the payload from Redis,
    and deletes it so it cannot be reused.
    """
    if error_desc := token_data.get("error_description"):
        raise OAuthCallbackError(error_desc)

    if not state:
        raise OAuthCallbackError("No state")

    cookie_nonce = request.cookies.get(settings.OAUTH_STATE_COOKIE_KEY)
    if cookie_nonce is None or not secrets.compare_digest(state, cookie_nonce):
        raise OAuthCallbackError("Invalid session cookie")

    payload = await retrieve_oauth_state(redis, state, type=type)
    await delete_oauth_state(redis, state, type=type)
    return payload
