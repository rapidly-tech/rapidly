"""Tests for ``rapidly/admin/dependencies.py``.

Admin auth dependency. Three load-bearing surfaces:

- ``get_admin`` reads the regular user session AND the impersonation
  cookie's session. The IMPERSONATION session takes PRECEDENCE so
  the real admin keeps their privileges while acting-as another
  user. Drift to use the regular session would let impersonation
  ESCALATE: an admin acting-as a non-admin would lose admin
  privileges (acceptable) BUT a non-admin acting-as an admin
  would gain them (privilege escalation).
- No resolved session → ``HTTPException(401, Unauthorized)``.
  Drift to 403 would conflate "not logged in" with "not allowed",
  breaking the frontend's "redirect to login" branch.
- Resolved-but-non-admin session → ``HTTPException(403, Forbidden)``.
  Drift to 401 would force a logged-in user back to the login
  page (UX regression) instead of showing the "you're not an
  admin" copy.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.exceptions import HTTPException

from rapidly.admin import dependencies as M
from rapidly.admin.dependencies import get_admin


def _user_session(*, is_admin: bool) -> Any:
    """Build a UserSession-like mock with the attrs get_admin reads."""
    sess = MagicMock()
    user = MagicMock()
    user.is_admin = is_admin
    sess.user = user
    return sess


def _request_and_session() -> tuple[Any, Any]:
    request = MagicMock()
    request.headers = {}
    request.cookies = {}
    return request, MagicMock()


def _patch_authenticate(
    monkeypatch: pytest.MonkeyPatch,
    *,
    user_session: Any | None,
    impersonation: Any | None,
) -> Any:
    """Patch auth_service.authenticate so first call returns user_session
    and second call (with impersonation cookie kwarg) returns impersonation."""
    fake = MagicMock()

    async def fake_authenticate(
        session: Any, request: Any, cookie: str | None = None
    ) -> Any:
        # The second call passes the impersonation cookie via kwarg.
        if cookie is not None:
            return impersonation
        return user_session

    fake.authenticate = fake_authenticate
    monkeypatch.setattr(M, "auth_service", fake)
    return fake


@pytest.mark.asyncio
class TestGetAdmin:
    async def test_raises_401_when_no_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: no session → 401 Unauthorized. Drift to 403 would
        # conflate "not logged in" with "not allowed" and break
        # the frontend's redirect-to-login branch.
        _patch_authenticate(monkeypatch, user_session=None, impersonation=None)
        request, session = _request_and_session()
        with pytest.raises(HTTPException) as exc:
            await get_admin(request, session)
        assert exc.value.status_code == 401

    async def test_raises_403_when_session_is_non_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: non-admin session → 403 Forbidden. Drift to 401
        # would force a logged-in user back to the login page
        # (UX regression).
        _patch_authenticate(
            monkeypatch,
            user_session=_user_session(is_admin=False),
            impersonation=None,
        )
        request, session = _request_and_session()
        with pytest.raises(HTTPException) as exc:
            await get_admin(request, session)
        assert exc.value.status_code == 403

    async def test_returns_admin_session_when_admin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        admin_sess = _user_session(is_admin=True)
        _patch_authenticate(monkeypatch, user_session=admin_sess, impersonation=None)
        request, session = _request_and_session()
        result = await get_admin(request, session)
        assert result is admin_sess


@pytest.mark.asyncio
class TestImpersonationPrecedence:
    async def test_impersonation_session_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # LOAD-BEARING SECURITY: when an impersonation cookie is
        # present, ITS session (the real admin) is the
        # authoritative identity. Drift to use the regular session
        # would mean a non-admin acting-as an admin gains admin
        # privileges (privilege escalation).
        regular = _user_session(is_admin=False)  # The impersonated user
        admin = _user_session(is_admin=True)  # The real admin
        _patch_authenticate(monkeypatch, user_session=regular, impersonation=admin)
        request, session = _request_and_session()
        result = await get_admin(request, session)
        # Returns the admin (impersonation) session, NOT the
        # impersonated regular user.
        assert result is admin

    async def test_impersonation_with_non_admin_real_user_still_403(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: if SOMEHOW the impersonation cookie carries a
        # non-admin session (shouldn't happen — only admins can
        # set it — but defensive), the 403 gate still fires.
        regular = _user_session(is_admin=True)
        non_admin_imp = _user_session(is_admin=False)
        _patch_authenticate(
            monkeypatch, user_session=regular, impersonation=non_admin_imp
        )
        request, session = _request_and_session()
        with pytest.raises(HTTPException) as exc:
            await get_admin(request, session)
        # Pin: the impersonation session is checked, NOT the
        # regular admin session.
        assert exc.value.status_code == 403

    async def test_uses_impersonation_cookie_setting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the SECOND auth call uses the
        # ``IMPERSONATION_COOKIE_KEY`` setting (NOT a hardcoded
        # name). Drift to a hardcoded literal would silently
        # break multi-tenant deployments that override the key.
        from rapidly.config import settings

        captured_cookies: list[str] = []

        async def capturing_authenticate(
            session: Any, request: Any, cookie: str | None = None
        ) -> Any:
            if cookie is not None:
                captured_cookies.append(cookie)
            return None

        fake = MagicMock()
        fake.authenticate = capturing_authenticate
        monkeypatch.setattr(M, "auth_service", fake)

        request, session = _request_and_session()
        with pytest.raises(HTTPException):
            await get_admin(request, session)
        assert captured_cookies == [settings.IMPERSONATION_COOKIE_KEY]
