"""Tests for ``rapidly/integrations/google/actions.py``.

Google OAuth integration. Three load-bearing surfaces:

- Exception hierarchy: ``GoogleServiceError`` extends
  ``RapidlyError``; ``CannotLinkUnverifiedEmailError`` and
  ``AccountLinkedToAnotherUserError`` use status code 403 (the
  frontend's account-merge UX branches on 403). Drift to 400
  would blank out the special handling.
- ``_get_profile`` maps OIDC userinfo fields:
  * ``sub`` → ``id`` (OIDC standard subject claim)
  * ``email`` → ``email``
  * ``email_verified`` → ``email_verified``
  * ``picture`` → optional, falls back to None
  Drift to using ``id`` instead of ``sub`` would silently break
  every Google sign-in (Google's userinfo endpoint emits ``sub``).
- ``_get_profile`` calls the OIDC v1 userinfo endpoint, NOT the
  legacy Google+ ``/oauth2/v2/userinfo``. Drift to the legacy
  endpoint would 410-Gone on Google's side.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rapidly.errors import RapidlyError
from rapidly.integrations.google.actions import (
    AccountLinkedToAnotherUserError,
    CannotLinkUnverifiedEmailError,
    GoogleServiceError,
    _get_profile,
)


class TestExceptionHierarchy:
    def test_google_service_error_extends_rapidly_error(self) -> None:
        # Pin: callers in the OAuth handler catch on the base class
        # to render a generic OAuth-failure response.
        assert issubclass(GoogleServiceError, RapidlyError)

    def test_cannot_link_extends_service_error(self) -> None:
        assert issubclass(CannotLinkUnverifiedEmailError, GoogleServiceError)

    def test_account_linked_extends_service_error(self) -> None:
        assert issubclass(AccountLinkedToAnotherUserError, GoogleServiceError)


class TestCannotLinkUnverifiedEmailError:
    def test_includes_email_in_message(self) -> None:
        # Pin: the email is interpolated so the user knows which
        # account is conflicting. Drift to a generic message
        # would force a support ticket.
        err = CannotLinkUnverifiedEmailError(email="alice@gmail.com")
        assert "alice@gmail.com" in str(err)

    def test_uses_status_code_403(self) -> None:
        # Pin: the frontend's account-merge UX branches on 403.
        # Drift to 400 would blank out the special explanation
        # page and show a generic error toast.
        err = CannotLinkUnverifiedEmailError(email="x@y.com")
        assert err.status_code == 403

    def test_message_mentions_google_specifically(self) -> None:
        # Pin: the message names the provider so the user knows
        # which side to go fix verification on.
        err = CannotLinkUnverifiedEmailError(email="x@y.com")
        assert "Google" in str(err)


class TestAccountLinkedToAnotherUserError:
    def test_uses_status_code_403(self) -> None:
        err = AccountLinkedToAnotherUserError()
        assert err.status_code == 403

    def test_message_mentions_other_account(self) -> None:
        err = AccountLinkedToAnotherUserError()
        assert (
            "another user" in str(err).lower() or "another account" in str(err).lower()
        )


def _mock_oidc_response(payload: dict[str, Any]) -> Any:
    """Build a fake httpx response for the OIDC userinfo endpoint."""
    resp = MagicMock()
    resp.json = MagicMock(return_value=payload)
    resp.raise_for_status = MagicMock(return_value=None)
    return resp


@pytest.mark.asyncio
class TestGetProfile:
    async def test_maps_oidc_sub_to_id(self) -> None:
        # Pin: Google's OIDC userinfo emits ``sub`` (OIDC standard).
        # Drift to using ``id`` would always KeyError because the
        # legacy Google+ endpoint isn't being called.
        resp = _mock_oidc_response(
            {
                "sub": "112233445566",
                "email": "alice@gmail.com",
                "email_verified": True,
                "picture": "https://lh3.googleusercontent.com/a/x",
            }
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            profile = await _get_profile("token-abc")

        assert profile["id"] == "112233445566"
        assert profile["email"] == "alice@gmail.com"

    async def test_email_verified_passes_through(self) -> None:
        # Pin: unlike Microsoft and Apple, Google's verified flag
        # is real (Gmail accounts are auto-verified, Workspace
        # admin-managed accounts can be verified or not).
        # email_verified must NOT be hardcoded to True — the
        # account-link flow depends on the actual flag to decide
        # whether to merge with an existing email-only account.
        for verified in (True, False):
            resp = _mock_oidc_response(
                {
                    "sub": "x",
                    "email": "y@z.com",
                    "email_verified": verified,
                }
            )
            client = MagicMock()
            client.get = AsyncMock(return_value=resp)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)

            with patch("httpx.AsyncClient", return_value=client):
                profile = await _get_profile("t")

            assert profile["email_verified"] is verified

    async def test_picture_optional_falls_back_to_none(self) -> None:
        # Defensive: ``picture`` is optional in OIDC userinfo (the
        # user may not have a Google avatar). Pin the None
        # fallback so a regression to ``data["picture"]`` doesn't
        # KeyError on accounts without an avatar.
        resp = _mock_oidc_response(
            {
                "sub": "no-avatar",
                "email": "x@y.com",
                "email_verified": True,
            }
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            profile = await _get_profile("t")

        assert profile["picture"] is None

    async def test_picture_passes_through_when_present(self) -> None:
        url = "https://lh3.googleusercontent.com/a/picture-url"
        resp = _mock_oidc_response(
            {
                "sub": "x",
                "email": "y@z.com",
                "email_verified": True,
                "picture": url,
            }
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            profile = await _get_profile("t")

        assert profile["picture"] == url

    async def test_authorization_header_set(self) -> None:
        # Pin: Google requires "Bearer <token>" auth header on the
        # userinfo endpoint. Drift to a different scheme would
        # 401 every userinfo request.
        resp = _mock_oidc_response(
            {"sub": "x", "email": "y@z.com", "email_verified": True}
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            await _get_profile("my-token")

        client.get.assert_awaited_once()
        kwargs = client.get.call_args.kwargs
        assert kwargs["headers"]["Authorization"] == "Bearer my-token"

    async def test_calls_oidc_userinfo_endpoint(self) -> None:
        # Pin: the OIDC v1 endpoint, NOT the legacy Google+ one.
        # ``openidconnect.googleapis.com/v1/userinfo`` is the
        # supported endpoint; ``/oauth2/v2/userinfo`` was
        # deprecated and will eventually 410-Gone.
        resp = _mock_oidc_response(
            {"sub": "x", "email": "y@z.com", "email_verified": True}
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            await _get_profile("t")

        url_arg = client.get.call_args.args[0]
        assert url_arg == "https://openidconnect.googleapis.com/v1/userinfo"

    async def test_raise_for_status_is_called(self) -> None:
        # Pin: an HTTP error from the userinfo endpoint propagates
        # via ``raise_for_status``. Without it, a 401 (expired
        # token) would silently return malformed data and crash
        # downstream on the missing ``sub`` key.
        resp = _mock_oidc_response(
            {"sub": "x", "email": "y@z.com", "email_verified": True}
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            await _get_profile("t")

        resp.raise_for_status.assert_called_once()

    async def test_returns_typeddict_with_four_fields(self) -> None:
        # Pin the profile shape: id, email, email_verified, picture.
        # Drift that added optional fields would silently re-shape
        # callers (TypedDict is structural).
        resp = _mock_oidc_response(
            {
                "sub": "x",
                "email": "y@z.com",
                "email_verified": True,
                "picture": "url",
                # Extra fields like ``hd`` (hosted domain) are
                # ignored — pin that they don't leak into the
                # returned dict.
                "hd": "example.com",
                "name": "Y",
            }
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            profile = await _get_profile("t")

        assert set(profile.keys()) == {"id", "email", "email_verified", "picture"}
