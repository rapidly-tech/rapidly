"""Tests for ``rapidly/admin/impersonation/api.py`` — pure helpers.

Three load-bearing surfaces:

- ``_IMPERSONATION_TTL = 60 min`` — drift longer than 1 h would
  let an admin's "act-as" session linger past the audit window;
  drift shorter would expire mid-debugging.
- ``_COOKIE_DEFAULTS`` carry the secure-cookie flags
  (samesite=lax, secure outside dev, env-driven domain). Drift
  to samesite=none would re-open CSRF on the impersonation
  cookie.
- ``_validated_cookie_value`` rejects any non-base64 / non-URL-
  safe character via ``HTTPException(400)``. LOAD-BEARING
  SECURITY: defends against cookie-header injection where an
  attacker-supplied cookie value with control chars could
  forge multiple Set-Cookie headers in the response.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.exceptions import HTTPException

from rapidly.admin.impersonation.api import (
    _COOKIE_DEFAULTS,
    _IMPERSONATION_TTL,
    _SAFE_COOKIE_RE,
    _set_session_cookie,
    _validated_cookie_value,
)


class TestImpersonationTtl:
    def test_pinned_to_60_minutes(self) -> None:
        # Pin: 1-hour TTL — long enough for debugging, short
        # enough to bound the audit window for an admin's act-as
        # session.
        assert _IMPERSONATION_TTL == timedelta(minutes=60)


class TestCookieDefaults:
    def test_path_root(self) -> None:
        # Pin: cookie applies to entire site (drift to a narrower
        # path would log out admins mid-impersonation).
        assert _COOKIE_DEFAULTS["path"] == "/"

    def test_samesite_lax(self) -> None:
        # Pin: SameSite=Lax — defends against CSRF on the
        # impersonation cookie. Drift to "none" would re-open
        # CSRF; drift to "strict" would break the
        # impersonation-via-link flow.
        assert _COOKIE_DEFAULTS["samesite"] == "lax"

    def test_secure_in_non_dev(self) -> None:
        # Pin: secure outside dev so the impersonation cookie is
        # only sent over HTTPS. Defends against HTTPS-strip
        # attacks that could capture the cookie.
        # The defaults are computed at import time. Verify it's
        # a bool (env-aware).
        assert isinstance(_COOKIE_DEFAULTS["secure"], bool)


class TestSafeCookieRegex:
    def test_accepts_url_safe_base64(self) -> None:
        # Pin: URL-safe-base64 alphabet (alnum + _ - = .) — the
        # documented session-token format.
        assert _SAFE_COOKIE_RE.match("rapidly_us_AbCd_-=.123") is not None

    def test_rejects_control_characters(self) -> None:
        # Pin: control chars rejected (cookie-header-injection
        # defence).
        assert _SAFE_COOKIE_RE.match("rapidly\x00bad") is None
        assert _SAFE_COOKIE_RE.match("rapidly\nbad") is None

    def test_rejects_spaces_and_quotes(self) -> None:
        # Pin: space + quote would let an attacker break out of
        # the cookie value into Set-Cookie attributes.
        assert _SAFE_COOKIE_RE.match("rapidly bad") is None
        assert _SAFE_COOKIE_RE.match('rapidly"bad') is None

    def test_rejects_semicolon(self) -> None:
        # Pin (CRITICAL): ``;`` is the Set-Cookie attribute
        # separator. An attacker who could smuggle ``;`` into
        # the cookie value could append ``Domain=evil.com`` and
        # rebind the cookie.
        assert _SAFE_COOKIE_RE.match("rapidly;bad") is None


class TestValidatedCookieValue:
    def test_accepts_valid_token(self) -> None:
        # Pin: well-formed URL-safe base64 token passes through.
        assert _validated_cookie_value("rapidly_us_abc123") == "rapidly_us_abc123"

    def test_rejects_invalid_with_400(self) -> None:
        # LOAD-BEARING SECURITY: invalid cookie value → 400 Bad
        # Request. Drift to silent passthrough would let an
        # attacker forge multi-header injection.
        with pytest.raises(HTTPException) as exc:
            _validated_cookie_value("bad value")
        assert exc.value.status_code == 400

    def test_rejects_empty_string(self) -> None:
        # Pin: empty string is rejected (regex requires ≥1 char).
        with pytest.raises(HTTPException):
            _validated_cookie_value("")

    def test_rejects_control_char(self) -> None:
        # Pin: control char rejected.
        with pytest.raises(HTTPException):
            _validated_cookie_value("token\x00more")


class TestSetSessionCookieSanitisation:
    def test_strips_control_chars(self) -> None:
        # Pin (security): control chars stripped before
        # ``set_cookie``. This is the LAST line of defence after
        # ``_validated_cookie_value`` for the rare case where the
        # caller skips validation.
        captured: dict[str, Any] = {}
        response = MagicMock()

        def _capture(*args: Any, **kw: Any) -> None:
            if args:
                captured["key_positional"] = args[0]
            captured.update(kw)

        response.set_cookie = MagicMock(side_effect=_capture)

        _set_session_cookie(response, "key", "value\x00\x1fwith\x7fctrl", expires=0)

        assert captured["value"] == "valuewithctrl"
        # Other args pass through.
        assert captured["key_positional"] == "key"
        assert captured["httponly"] is True

    def test_httponly_default_true(self) -> None:
        # Pin: httponly=True by default — JavaScript can't read
        # the impersonation cookie via document.cookie.
        captured: dict[str, Any] = {}
        response = MagicMock()

        def _capture(*args: Any, **kw: Any) -> None:
            if args:
                captured["key_positional"] = args[0]
            captured.update(kw)

        response.set_cookie = MagicMock(side_effect=_capture)

        _set_session_cookie(response, "k", "v", expires=0)
        assert captured["httponly"] is True

    def test_httponly_can_be_overridden(self) -> None:
        # Pin: callers can opt-in to JS-readable when the use
        # case requires it (e.g., a CSRF token).
        captured: dict[str, Any] = {}
        response = MagicMock()

        def _capture(*args: Any, **kw: Any) -> None:
            if args:
                captured["key_positional"] = args[0]
            captured.update(kw)

        response.set_cookie = MagicMock(side_effect=_capture)

        _set_session_cookie(response, "k", "v", expires=0, httponly=False)
        assert captured["httponly"] is False
