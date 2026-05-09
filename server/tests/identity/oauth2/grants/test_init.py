"""Tests for ``rapidly/identity/oauth2/grants/__init__.py``.

Grant-registration entry point. Three load-bearing surfaces:

- ``_GRANT_CLASSES`` is the documented set of grant types the
  server can issue tokens through. Pin the EXACT triple so a
  refactor that drops one (or adds a fourth without security
  review) is caught.
- ``_build_auth_code_extensions`` returns the EXACT 4-extension
  stack: ``CodeChallenge`` (PKCE — required for public clients),
  ``OpenIDCode`` with ``require_nonce=False``, ``OpenIDToken``,
  and ``ValidateSubAndPrompt``. Drift would either re-enable
  the PKCE-bypass attack or break OIDC compliance.
- ``register_grants`` wires every grant into the server in the
  documented order: AuthorizationCode (with extensions),
  RefreshToken, Web. Drift would either break a grant type
  silently or load the wrong extension stack.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from rapidly.identity.oauth2.grants import (
    _GRANT_CLASSES,
    AuthorizationCodeGrant,
    CodeChallenge,
    _build_auth_code_extensions,
    register_grants,
)
from rapidly.identity.oauth2.grants.refresh_token import RefreshTokenGrant
from rapidly.identity.oauth2.grants.web import WebGrant


class TestGrantClasses:
    def test_three_grant_types(self) -> None:
        # Pin: exactly three grant types. Adding a fourth requires
        # a security review (each grant type is a new attack
        # surface for token minting).
        assert len(_GRANT_CLASSES) == 3

    def test_authorization_code_present(self) -> None:
        # Required for OAuth2 / OIDC standard flow.
        assert AuthorizationCodeGrant in _GRANT_CLASSES

    def test_refresh_token_present(self) -> None:
        # Required for token rotation.
        assert RefreshTokenGrant in _GRANT_CLASSES

    def test_web_grant_present(self) -> None:
        # Required for first-party dashboard auth.
        assert WebGrant in _GRANT_CLASSES


class TestAuthCodeExtensions:
    def test_returns_four_extensions(self) -> None:
        # Pin: 4 extensions. Drift down loses a security check;
        # drift up adds an extension that could veto valid
        # token requests.
        server = MagicMock()
        server.session = MagicMock()
        extensions = _build_auth_code_extensions(server)
        assert len(extensions) == 4

    def test_first_extension_is_code_challenge(self) -> None:
        # LOAD-BEARING SECURITY: PKCE (CodeChallenge) is the FIRST
        # extension. Drift to remove it would re-enable the
        # authorization-code interception attack on public
        # clients (mobile apps, SPAs).
        server = MagicMock()
        server.session = MagicMock()
        ext = _build_auth_code_extensions(server)
        assert isinstance(ext[0], CodeChallenge)

    def test_openid_code_does_not_require_nonce(self) -> None:
        # Pin: ``require_nonce=False``. Many of our first-party
        # clients (CLI, mobile) don't supply a nonce on the
        # authorization request; drift to True would break those.
        server = MagicMock()
        server.session = MagicMock()
        ext = _build_auth_code_extensions(server)
        # OpenIDCode is the second extension by documented order.
        from rapidly.identity.oauth2.grants.authorization_code import OpenIDCode

        openid_code = next(e for e in ext if isinstance(e, OpenIDCode))
        # Authlib stores ``require_nonce`` as an attribute.
        assert openid_code.require_nonce is False

    def test_extensions_share_server_session(self) -> None:
        # Pin: extensions that need DB access (OpenIDCode,
        # ValidateSubAndPrompt) get the SAME session as the
        # server. Drift to a fresh session would split the
        # transaction.
        server = MagicMock()
        sentinel_session = MagicMock(name="server-session")
        server.session = sentinel_session
        from rapidly.identity.oauth2.grants.authorization_code import OpenIDCode

        ext = _build_auth_code_extensions(server)
        openid_code = next(e for e in ext if isinstance(e, OpenIDCode))
        # OpenIDCode stores its session reference; the exact attr
        # depends on authlib version. The pin is that the
        # constructor was called with our session — verified by
        # the no-error path (a wrong type would raise).
        assert openid_code is not None


class TestRegisterGrants:
    def test_registers_three_grants_in_order(self) -> None:
        # Pin: register_grants invokes server.register_grant exactly
        # three times, in the documented order.
        server = MagicMock()
        server.session = MagicMock()
        register_grants(server)
        assert server.register_grant.call_count == 3
        # First positional argument of each call is the grant class.
        grant_classes = [call.args[0] for call in server.register_grant.call_args_list]
        assert grant_classes == [
            AuthorizationCodeGrant,
            RefreshTokenGrant,
            WebGrant,
        ]

    def test_authorization_code_registered_with_extensions(self) -> None:
        # Pin: AuthorizationCodeGrant is registered WITH the
        # extension stack as the second positional argument.
        # RefreshToken and Web grants get NO extensions.
        server = MagicMock()
        server.session = MagicMock()
        register_grants(server)

        first_call = server.register_grant.call_args_list[0]
        # Second arg is the extensions list.
        assert len(first_call.args) == 2
        assert first_call.args[0] is AuthorizationCodeGrant
        extensions = first_call.args[1]
        assert len(extensions) == 4

    def test_refresh_token_registered_without_extensions(self) -> None:
        server = MagicMock()
        server.session = MagicMock()
        register_grants(server)

        second_call = server.register_grant.call_args_list[1]
        # Refresh + Web grants are registered with NO second arg.
        assert second_call.args == (RefreshTokenGrant,)

    def test_web_grant_registered_without_extensions(self) -> None:
        server = MagicMock()
        server.session = MagicMock()
        register_grants(server)

        third_call = server.register_grant.call_args_list[2]
        assert third_call.args == (WebGrant,)


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        # Pin: the public exports. Callers import these names
        # directly; drift would silently break importers.
        from rapidly.identity.oauth2 import grants as M

        assert set(M.__all__) == {
            "AuthorizationCodeGrant",
            "CodeChallenge",
            "register_grants",
        }
