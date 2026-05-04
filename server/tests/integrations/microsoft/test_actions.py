"""Tests for ``rapidly/integrations/microsoft/actions.py``.

Microsoft Graph OAuth integration. Three load-bearing surfaces:

- Exception hierarchy: ``MicrosoftServiceError`` extends
  ``RapidlyError``; ``CannotLinkUnverifiedEmailError`` and
  ``AccountLinkedToAnotherUserError`` use status code 403 (the
  account-linking error responses MUST be 403, not 400 — the
  frontend's account-merge UX branches on 403 specifically).
  ``NoEmailError`` extends the service base.
- ``_get_profile`` resolves the email field as ``mail`` ||
  ``userPrincipalName`` || raise ``NoEmailError``. Microsoft
  consumer accounts populate ``mail`` while work accounts use
  ``userPrincipalName``; mis-prioritising would block half the
  user base.
- ``_get_profile`` always sets ``email_verified=True`` because
  Microsoft Graph requires verification at registration. A
  regression to ``False`` would force every Microsoft sign-in
  through the unverified-email flow (which doesn't exist for
  this provider) and break Microsoft login entirely.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rapidly.errors import RapidlyError
from rapidly.integrations.microsoft.actions import (
    AccountLinkedToAnotherUserError,
    CannotLinkUnverifiedEmailError,
    MicrosoftServiceError,
    NoEmailError,
    _get_profile,
)


class TestExceptionHierarchy:
    def test_microsoft_service_error_extends_rapidly_error(self) -> None:
        # Pin: callers in ``rapidly/identity/oauth2/``  catch on the
        # base class to render a generic OAuth-failure response.
        # Drift to plain Exception would let Microsoft errors
        # bypass the standard error handler.
        assert issubclass(MicrosoftServiceError, RapidlyError)

    def test_no_email_error_extends_service_error(self) -> None:
        assert issubclass(NoEmailError, MicrosoftServiceError)

    def test_cannot_link_extends_service_error(self) -> None:
        assert issubclass(CannotLinkUnverifiedEmailError, MicrosoftServiceError)

    def test_account_linked_extends_service_error(self) -> None:
        assert issubclass(AccountLinkedToAnotherUserError, MicrosoftServiceError)


class TestNoEmailError:
    def test_message_explains_remediation(self) -> None:
        # Pin: the user-facing message tells them HOW to recover
        # (add an email to their Microsoft account). Drift to a
        # bare error code would leave the user stuck.
        err = NoEmailError()
        assert "Microsoft account" in str(err)
        assert "email" in str(err).lower()


class TestCannotLinkUnverifiedEmailError:
    def test_includes_email_in_message(self) -> None:
        # Pin: the email is interpolated so the user knows which
        # account is conflicting. Drift to a generic message
        # would force a support ticket.
        err = CannotLinkUnverifiedEmailError(email="alice@example.com")
        assert "alice@example.com" in str(err)

    def test_uses_status_code_403(self) -> None:
        # Pin: the frontend's account-merge UX branches on 403
        # specifically. Drift to 400 would blank out the special
        # explanation page and show a generic error toast.
        err = CannotLinkUnverifiedEmailError(email="x@y.com")
        # ``RapidlyError`` carries the status code as a public attr.
        assert err.status_code == 403


class TestAccountLinkedToAnotherUserError:
    def test_uses_status_code_403(self) -> None:
        # Same UX pin as the unverified-email error. Drift to 400
        # would break the cross-account-conflict handler.
        err = AccountLinkedToAnotherUserError()
        assert err.status_code == 403

    def test_message_mentions_other_account(self) -> None:
        err = AccountLinkedToAnotherUserError()
        assert (
            "another user" in str(err).lower() or "another account" in str(err).lower()
        )


def _mock_graph_response(payload: dict[str, Any]) -> Any:
    """Build a fake httpx response object with the Graph API payload."""
    resp = MagicMock()
    resp.json = MagicMock(return_value=payload)
    resp.raise_for_status = MagicMock(return_value=None)
    return resp


@pytest.mark.asyncio
class TestGetProfile:
    async def test_consumer_account_uses_mail_field(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: Microsoft consumer accounts populate ``mail`` —
        # tested first because it's the more common case.
        resp = _mock_graph_response(
            {
                "id": "abc123",
                "mail": "alice@outlook.com",
                "userPrincipalName": "alice_outlook.com#EXT#@x.onmicrosoft.com",
                "displayName": "Alice",
            }
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            profile = await _get_profile("token-abc")

        assert profile["email"] == "alice@outlook.com"
        assert profile["id"] == "abc123"
        assert profile["display_name"] == "Alice"

    async def test_work_account_falls_back_to_user_principal_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: work / school accounts often have ``mail=None`` and
        # ``userPrincipalName`` carries the email. Drift to using
        # ``mail`` only would block every Office 365 user.
        resp = _mock_graph_response(
            {
                "id": "work-1",
                "mail": None,
                "userPrincipalName": "bob@contoso.com",
                "displayName": "Bob",
            }
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            profile = await _get_profile("t")

        assert profile["email"] == "bob@contoso.com"

    async def test_no_email_raises_no_email_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the explicit error type lets the OAuth handler
        # surface the friendly "add an email to your Microsoft
        # account" message. Drift to a bare ``ValueError`` would
        # show the user a generic 500.
        resp = _mock_graph_response(
            {"id": "no-email", "mail": None, "userPrincipalName": None}
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(NoEmailError):
                await _get_profile("t")

    async def test_email_verified_is_always_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: Microsoft Graph requires email verification at
        # registration, so emails are considered pre-verified.
        # Drift to ``False`` would force every Microsoft sign-in
        # through the unverified-email flow (which doesn't exist
        # for this provider) and break Microsoft login.
        resp = _mock_graph_response({"id": "x", "mail": "y@z.com", "displayName": "Y"})
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            profile = await _get_profile("t")

        assert profile["email_verified"] is True

    async def test_picture_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: Graph API doesn't include picture URLs in /me; the
        # bridge always returns None for ``picture``. A regression
        # that pulled from a non-existent JSON key would crash on
        # the first profile fetch.
        resp = _mock_graph_response({"id": "x", "mail": "y@z.com", "displayName": "Y"})
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            profile = await _get_profile("t")

        assert profile["picture"] is None

    async def test_display_name_can_be_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: Graph occasionally omits ``displayName`` for
        # service accounts. Pin the None fallback.
        resp = _mock_graph_response({"id": "x", "mail": "y@z.com"})
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            profile = await _get_profile("t")

        assert profile["display_name"] is None

    async def test_authorization_header_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the Graph API auth header format: "Bearer <token>".
        # Drift to "Token" or omitted prefix would 401 every
        # request (Microsoft Graph rejects non-Bearer auth).
        resp = _mock_graph_response({"id": "x", "mail": "y@z.com", "displayName": "Y"})
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            await _get_profile("my-token")

        client.get.assert_awaited_once()
        kwargs = client.get.call_args.kwargs
        assert kwargs["headers"]["Authorization"] == "Bearer my-token"

    async def test_calls_graph_me_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the v1.0 endpoint URL — drift to /beta would return
        # an unstable schema; drift to /users/<id> would 404.
        resp = _mock_graph_response({"id": "x", "mail": "y@z.com", "displayName": "Y"})
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=client):
            await _get_profile("t")

        url_arg = client.get.call_args.args[0]
        assert url_arg == "https://graph.microsoft.com/v1.0/me"
