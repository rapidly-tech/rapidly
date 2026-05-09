"""Tests for ``rapidly/identity/oauth2/dependencies.py``.

OAuth2 token extraction + authorization-server lifecycle. Three
load-bearing surfaces:

- ``get_optional_token`` returns a ``(token, had_header)`` tuple
  so downstream code can distinguish "no header" (anonymous) from
  "invalid token" (401 with InvalidTokenError). Drift to a single
  ``Optional[token]`` would lose the distinction and turn every
  anonymous request into a 401.
- Bearer-scheme matching is case-insensitive — RFC 6750 §2.1
  documents ``Bearer`` with capital B but real-world clients send
  ``bearer``, ``BEARER``, or even ``BeArEr``. Drift to a strict
  case match would 401 ~5% of clients.
- ``get_authorization_server`` commits the sync session on success
  and rolls back on exception. Drift would either lose writes
  (no commit) or leak partial writes (no rollback).
- ``openid_scheme`` is wired to ``/.well-known/openid-configuration``
  with ``auto_error=False`` so the FastAPI dependency yields None
  on missing header rather than raising 401 itself (the explicit
  ``get_token`` raise gives us the InvalidTokenError vs Unauthorized
  distinction above).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.security import OpenIdConnect

from rapidly.errors import Unauthorized
from rapidly.identity.oauth2 import dependencies as M
from rapidly.identity.oauth2.dependencies import (
    get_authorization_server,
    get_optional_token,
    get_token,
    openid_scheme,
)
from rapidly.identity.oauth2.exceptions import InvalidTokenError


class TestOpenidScheme:
    def test_is_openid_connect(self) -> None:
        # Pin: ``OpenIdConnect`` (NOT ``OAuth2PasswordBearer``).
        # Drift would change the OpenAPI security advertisement,
        # confusing API clients that read the spec.
        assert isinstance(openid_scheme, OpenIdConnect)

    def test_scheme_name(self) -> None:
        # Pin: ``oidc`` — Swagger UI's "Authorize" button reads
        # this to label the input.
        assert openid_scheme.scheme_name == "oidc"

    def test_auto_error_disabled(self) -> None:
        # Pin: ``auto_error=False`` so the dependency yields None
        # on a missing header rather than raising 401 itself.
        # ``get_token`` raises explicitly with the right error
        # type (Unauthorized vs InvalidTokenError) downstream.
        assert openid_scheme.auto_error is False

    def test_openid_configuration_url(self) -> None:
        # Pin: the discovery URL points at the standard OIDC path.
        # Drift would break any client that does discovery.
        scheme = openid_scheme.model.openIdConnectUrl  # type: ignore[attr-defined]
        assert scheme == "/.well-known/openid-configuration"


@pytest.mark.asyncio
class TestGetOptionalToken:
    async def _setup(
        self, monkeypatch: pytest.MonkeyPatch, *, token: object | None
    ) -> Any:
        oauth2_service = MagicMock()
        oauth2_service.get_by_access_token = AsyncMock(return_value=token)
        monkeypatch.setattr(M, "oauth2_token_service", oauth2_service)
        return oauth2_service

    async def test_no_header_returns_none_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: missing/empty Authorization → (None, False).
        # Downstream ``get_token`` uses had_header=False to raise
        # Unauthorized (NOT InvalidTokenError) — different status
        # codes on the wire.
        await self._setup(monkeypatch, token=None)
        result = await get_optional_token(authorization="", session=MagicMock())
        assert result == (None, False)

    async def test_non_bearer_scheme_returns_none_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a non-bearer scheme (Basic / Digest / weird) is
        # treated as "no header" rather than "invalid token".
        # Otherwise ``Authorization: Basic xxx`` would 401 with
        # the WWW-Authenticate=Bearer challenge — confusing.
        await self._setup(monkeypatch, token=None)
        result = await get_optional_token(
            authorization="Basic dXNlcjpwYXNz", session=MagicMock()
        )
        assert result == (None, False)

    async def test_bearer_scheme_is_case_insensitive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``bearer`` / ``Bearer`` / ``BEARER`` all match.
        # RFC 6750 §2.1 documents Bearer but real clients send
        # all three; drift to strict case match would 401 ~5%
        # of API users.
        token = MagicMock()
        await self._setup(monkeypatch, token=token)

        for scheme_str in ("Bearer abc", "bearer abc", "BEARER abc", "BeArEr abc"):
            result = await get_optional_token(
                authorization=scheme_str, session=MagicMock()
            )
            assert result == (token, True), f"failed for {scheme_str!r}"

    async def test_bearer_with_unknown_token_returns_none_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: a bearer header WITH a token that doesn't resolve
        # in DB returns (None, True). The True flag is critical:
        # downstream raises InvalidTokenError (401 with
        # WWW-Authenticate including ``invalid_token`` description)
        # rather than the bare Unauthorized used for missing
        # headers.
        await self._setup(monkeypatch, token=None)
        result = await get_optional_token(
            authorization="Bearer unknown-xyz", session=MagicMock()
        )
        assert result == (None, True)

    async def test_calls_oauth2_token_service_with_raw_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the bare token (without "Bearer " prefix) is what
        # ``oauth2_token_service.get_by_access_token`` receives.
        # Drift would either send the prefix in the DB lookup
        # (404 every token) or strip too much (silent token
        # corruption).
        svc = await self._setup(monkeypatch, token=None)
        session = MagicMock()
        await get_optional_token(authorization="Bearer my-token-abc", session=session)
        svc.get_by_access_token.assert_awaited_once_with(session, "my-token-abc")


@pytest.mark.asyncio
class TestGetToken:
    async def test_raises_invalid_token_error_when_header_present_but_token_missing(
        self,
    ) -> None:
        # Pin: had_header=True + token=None → InvalidTokenError
        # (so the WWW-Authenticate response has invalid_token
        # description, telling the client the token is bad
        # vs. completely absent).
        with pytest.raises(InvalidTokenError):
            await get_token(credentials=(None, True))

    async def test_raises_unauthorized_when_no_header(self) -> None:
        # Pin: had_header=False + token=None → Unauthorized
        # (anonymous request, no token to invalidate).
        with pytest.raises(Unauthorized):
            await get_token(credentials=(None, False))

    async def test_returns_token_when_present(self) -> None:
        token = MagicMock()
        result = await get_token(credentials=(token, True))
        assert result is token


class TestGetAuthorizationServer:
    def _setup_request(self, monkeypatch: pytest.MonkeyPatch, *, session: Any) -> Any:
        request = MagicMock()
        maker = MagicMock(return_value=session)
        request.state.sync_sessionmaker = maker
        # Stub AuthorizationServer.build so we don't need a real
        # OAuth2 server to exercise the lifecycle.
        sentinel_server = object()
        monkeypatch.setattr(
            "rapidly.identity.oauth2.dependencies.AuthorizationServer.build",
            classmethod(lambda cls, s: sentinel_server),
        )
        return request, maker, sentinel_server

    def test_commits_session_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: the with-block exits cleanly → ``session.commit()``
        # is called. Drift would lose writes the grant handlers
        # made.
        sync_session = MagicMock()
        # Make the session usable as a context manager.
        sync_session.__enter__ = MagicMock(return_value=sync_session)
        sync_session.__exit__ = MagicMock(return_value=False)

        request, _, sentinel = self._setup_request(monkeypatch, session=sync_session)

        gen = get_authorization_server(request)
        server = next(gen)
        assert server is sentinel
        # Closing the generator triggers the success branch.
        with pytest.raises(StopIteration):
            next(gen)
        sync_session.commit.assert_called_once()
        sync_session.rollback.assert_not_called()

    def test_rolls_back_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin (load-bearing): an exception in the route handler
        # propagates AND ``session.rollback()`` is called. Drift
        # to no-rollback would leak partial writes from a failed
        # OAuth2 grant.
        sync_session = MagicMock()
        sync_session.__enter__ = MagicMock(return_value=sync_session)
        sync_session.__exit__ = MagicMock(return_value=False)

        request, _, _ = self._setup_request(monkeypatch, session=sync_session)

        gen = get_authorization_server(request)
        next(gen)
        with pytest.raises(RuntimeError, match="boom"):
            gen.throw(RuntimeError("boom"))
        sync_session.rollback.assert_called_once()
        sync_session.commit.assert_not_called()
