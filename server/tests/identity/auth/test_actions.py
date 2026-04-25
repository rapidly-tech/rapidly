"""Tests for ``rapidly/identity/auth/actions.py``.

User-session creation + cookie management. Five load-bearing
surfaces:

- ``USER_SESSION_TOKEN_PREFIX = "rapidly_us_"`` — the wire prefix
  that the auth middleware uses to distinguish session tokens
  from OAuth2 access tokens / customer-session tokens / etc.
  Drift would silently break token-class routing.
- ``_DEFAULT_LOGIN_SCOPES = [web_read, web_write]`` — every login
  gets exactly these two scopes. Drift to add an admin/billing
  scope would silently grant elevated privileges to every user.
- ``authenticate`` rejects non-ASCII session tokens — the same
  header-smuggling defence applied to bearer tokens. Drift would
  let a UTF-8 byte sequence exploit normalisation differences
  between proxy and app.
- ``authenticate`` returns None when ``user.can_authenticate``
  is False — banned / disabled users must not regain access via
  a still-valid cookie.
- ``_set_session_cookie`` security flags: ``secure=True`` outside
  dev (no HTTPS-stripping), ``httponly=True`` (no JS access),
  ``samesite="lax"`` (CSRF defence on top-level navigations).
  Optional ``domain`` for cross-subdomain cookies. Drift in any
  flag is a security regression.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from rapidly.identity.auth import actions as M
from rapidly.identity.auth.actions import (
    _DEFAULT_LOGIN_SCOPES,
    USER_SESSION_TOKEN_PREFIX,
    _set_session_cookie,
    authenticate,
)
from rapidly.identity.auth.scope import Scope


class TestTokenPrefix:
    def test_pinned_to_rapidly_us(self) -> None:
        # Pin: the auth middleware uses this prefix to route
        # token-class lookups (e.g., MEMBER_SESSION_TOKEN_PREFIX
        # vs. CUSTOMER_SESSION_TOKEN_PREFIX). Drift would silently
        # mis-route session tokens to a different DB lookup.
        assert USER_SESSION_TOKEN_PREFIX == "rapidly_us_"


class TestDefaultLoginScopes:
    def test_pinned_to_web_read_write(self) -> None:
        # LOAD-BEARING SECURITY: every login gets EXACTLY these two
        # scopes. Drift to add admin/billing scopes would silently
        # grant elevated privileges to every user. Drift to remove
        # one would lock users out of half the dashboard.
        assert _DEFAULT_LOGIN_SCOPES == [Scope.web_read, Scope.web_write]


class _Request:
    def __init__(self, *, cookies: dict[str, str], url_secure: bool = True) -> None:
        self.cookies = cookies
        self.url = MagicMock()
        self.url.is_secure = url_secure
        self.headers: dict[str, str] = {}


@pytest.mark.asyncio
class TestAuthenticate:
    def _patch_repo(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        user_session: Any | None,
    ) -> None:
        repo = MagicMock()
        repo.get_by_token = AsyncMock(return_value=user_session)
        repo_cls = MagicMock()
        repo_cls.from_session = MagicMock(return_value=repo)
        monkeypatch.setattr(M, "UserSessionRepository", repo_cls)

    async def test_returns_none_when_no_cookie(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_repo(monkeypatch, user_session=None)
        request = _Request(cookies={})
        result = await authenticate(MagicMock(), request)  # type: ignore[arg-type]
        assert result is None

    async def test_returns_none_when_token_non_ascii(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin (security): non-ASCII tokens rejected before the DB
        # lookup. Defends against header-smuggling via UTF-8
        # byte-sequence normalisation differences.
        from rapidly.config import settings

        self._patch_repo(monkeypatch, user_session=None)
        request = _Request(
            cookies={settings.USER_SESSION_COOKIE_KEY: "rapidly_us_tøken"}
        )
        result = await authenticate(MagicMock(), request)  # type: ignore[arg-type]
        assert result is None

    async def test_returns_none_when_token_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from rapidly.config import settings

        self._patch_repo(monkeypatch, user_session=None)
        request = _Request(
            cookies={settings.USER_SESSION_COOKIE_KEY: "rapidly_us_unknown"}
        )
        result = await authenticate(MagicMock(), request)  # type: ignore[arg-type]
        assert result is None

    async def test_returns_none_when_user_cannot_authenticate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin (security): even if the session token resolves, a
        # disabled / banned user must NOT regain access. Drift
        # would let a banned user re-authenticate via a still-
        # valid cookie.
        from rapidly.config import settings

        user_session = MagicMock()
        user_session.user = MagicMock()
        user_session.user.can_authenticate = False
        self._patch_repo(monkeypatch, user_session=user_session)

        request = _Request(
            cookies={settings.USER_SESSION_COOKIE_KEY: "rapidly_us_token"}
        )
        result = await authenticate(MagicMock(), request)  # type: ignore[arg-type]
        assert result is None

    async def test_returns_session_for_valid_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from rapidly.config import settings

        user_session = MagicMock()
        user_session.user = MagicMock()
        user_session.user.can_authenticate = True
        self._patch_repo(monkeypatch, user_session=user_session)

        request = _Request(
            cookies={settings.USER_SESSION_COOKIE_KEY: "rapidly_us_token"}
        )
        result = await authenticate(MagicMock(), request)  # type: ignore[arg-type]
        assert result is user_session


class TestSetSessionCookie:
    def _capture_cookie(
        self, *, dev_mode: bool, monkeypatch: pytest.MonkeyPatch
    ) -> dict[str, Any]:
        # Force the dev / non-dev branch on the secure flag.
        from rapidly.config import settings

        monkeypatch.setattr(settings, "is_development", lambda: dev_mode)

        captured: dict[str, Any] = {}
        response = MagicMock()
        response.set_cookie = MagicMock(side_effect=lambda **kw: captured.update(kw))
        request = MagicMock()
        _set_session_cookie(request, response, "rapidly_us_x", 1700000000)
        return captured

    def test_httponly_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: ``httponly=True`` so JavaScript can't read the
        # cookie via document.cookie. CRITICAL XSS defence —
        # drift would let a stored XSS exfiltrate session
        # tokens.
        kw = self._capture_cookie(dev_mode=False, monkeypatch=monkeypatch)
        assert kw["httponly"] is True

    def test_secure_in_non_dev(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: ``secure=True`` outside dev so the cookie is only
        # sent over HTTPS. Defends against HTTPS-stripping
        # attacks on coffee-shop wifi.
        kw = self._capture_cookie(dev_mode=False, monkeypatch=monkeypatch)
        assert kw["secure"] is True

    def test_secure_relaxed_in_dev(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: ``secure=False`` in development so localhost (HTTP)
        # works. Drift to ``True`` everywhere would block local
        # development.
        kw = self._capture_cookie(dev_mode=True, monkeypatch=monkeypatch)
        assert kw["secure"] is False

    def test_samesite_lax(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: ``samesite="lax"`` — CSRF defence on cross-site
        # POSTs while still allowing top-level navigations
        # (OAuth callbacks, marketing-link clicks). Drift to
        # "none" would re-open CSRF; drift to "strict" would
        # break OAuth callbacks.
        kw = self._capture_cookie(dev_mode=False, monkeypatch=monkeypatch)
        assert kw["samesite"] == "lax"

    def test_path_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: cookie path is "/" so it applies to the entire
        # site. Drift to a narrower path would log users out
        # when they navigate between dashboard pages.
        kw = self._capture_cookie(dev_mode=False, monkeypatch=monkeypatch)
        assert kw["path"] == "/"

    def test_uses_session_cookie_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: the cookie name comes from settings, NOT
        # hard-coded. Drift to a hard-coded name would break
        # multi-tenant deployments that override the key.
        from rapidly.config import settings

        kw = self._capture_cookie(dev_mode=False, monkeypatch=monkeypatch)
        assert kw["key"] == settings.USER_SESSION_COOKIE_KEY

    def test_domain_added_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: ``USER_SESSION_COOKIE_DOMAIN`` setting is honoured
        # when set. This enables cross-subdomain SSO (e.g.,
        # ``app.rapidly.tech`` + ``docs.rapidly.tech``).
        from rapidly.config import settings

        monkeypatch.setattr(settings, "is_development", lambda: False)
        monkeypatch.setattr(settings, "USER_SESSION_COOKIE_DOMAIN", ".rapidly.tech")

        captured: dict[str, Any] = {}
        response = MagicMock()
        response.set_cookie = MagicMock(side_effect=lambda **kw: captured.update(kw))
        _set_session_cookie(MagicMock(), response, "x", 0)
        assert captured["domain"] == ".rapidly.tech"

    def test_domain_omitted_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: when ``USER_SESSION_COOKIE_DOMAIN`` is empty/None,
        # the domain key is OMITTED (NOT passed as None — Starlette
        # treats None and missing differently).
        from rapidly.config import settings

        monkeypatch.setattr(settings, "is_development", lambda: False)
        monkeypatch.setattr(settings, "USER_SESSION_COOKIE_DOMAIN", "")

        captured: dict[str, Any] = {}
        response = MagicMock()
        response.set_cookie = MagicMock(side_effect=lambda **kw: captured.update(kw))
        _set_session_cookie(MagicMock(), response, "x", 0)
        assert "domain" not in captured

    def test_expires_int_passes_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: integer expiry (epoch ms) passes through as-is.
        from rapidly.config import settings

        monkeypatch.setattr(settings, "is_development", lambda: False)
        monkeypatch.setattr(settings, "USER_SESSION_COOKIE_DOMAIN", "")

        captured: dict[str, Any] = {}
        response = MagicMock()
        response.set_cookie = MagicMock(side_effect=lambda **kw: captured.update(kw))
        _set_session_cookie(MagicMock(), response, "x", 1700000000)
        assert captured["expires"] == 1700000000

    def test_expires_datetime_passes_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: datetime expiry (e.g. user_session.expires_at)
        # passes through as-is. Starlette's set_cookie accepts
        # both int and datetime — drift to forced-stringify
        # would break the format Starlette expects.
        from datetime import UTC

        from rapidly.config import settings

        monkeypatch.setattr(settings, "is_development", lambda: False)
        monkeypatch.setattr(settings, "USER_SESSION_COOKIE_DOMAIN", "")

        when = datetime(2026, 1, 1, tzinfo=UTC)
        captured: dict[str, Any] = {}
        response = MagicMock()
        response.set_cookie = MagicMock(side_effect=lambda **kw: captured.update(kw))
        _set_session_cookie(MagicMock(), response, "x", when)
        assert captured["expires"] == when
