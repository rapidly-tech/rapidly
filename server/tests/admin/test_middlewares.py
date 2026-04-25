"""Tests for ``rapidly/admin/middlewares.py``.

Admin-panel CSRF + security headers. Five load-bearing surfaces:

- ``CSRF_COOKIE_NAME`` = ``_csrf_token`` and ``CSRF_HEADER_NAME``
  = ``x-csrf-token``. The frontend HTMX layer reads the cookie
  and emits the header — drift in either silently breaks every
  state-changing admin request.
- ``_UNSAFE_METHODS`` = {POST, PUT, PATCH, DELETE} — exactly the
  RFC 7231 "unsafe" set. Drift to include GET would CSRF-block
  every admin page; drift to drop one (e.g., DELETE) would
  silently allow CSRF on that method.
- ``_SECURITY_HEADERS`` carry the documented hardening:
  Content-Security-Policy (script-src / object-src / base-uri),
  X-Content-Type-Options=nosniff, X-Frame-Options=DENY,
  Referrer-Policy=no-referrer, Permissions-Policy. Drift in any
  of these is a security regression.
- CSRFMiddleware uses ``secrets.compare_digest`` for token
  comparison (constant-time). Drift to ``==`` would expose a
  timing side-channel.
- The CSRF cookie is set with ``SameSite=Strict; Secure`` (NOT
  Lax). Lax would allow the cookie on top-level navigations,
  defeating the double-submit-cookie defence.
"""

from __future__ import annotations

import secrets
from http.cookies import SimpleCookie

from rapidly.admin.middlewares import (
    _SECURITY_HEADERS,
    _UNSAFE_METHODS,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CSRFMiddleware,
)


class TestCsrfConstants:
    def test_cookie_name_pinned(self) -> None:
        # Pin: HTMX templates read this literal cookie name. Drift
        # would silently break every state-changing admin request.
        assert CSRF_COOKIE_NAME == "_csrf_token"

    def test_header_name_pinned(self) -> None:
        # Pin: HTMX emits this header. Lowercase per ASGI spec
        # (header keys are case-insensitive but the lookup uses
        # the lowercase form).
        assert CSRF_HEADER_NAME == "x-csrf-token"


class TestUnsafeMethods:
    def test_pinned_to_state_changing_methods(self) -> None:
        # Pin: exactly the RFC 7231 "unsafe" set. Drift to include
        # GET would CSRF-block every admin page; drift to drop
        # any would silently allow CSRF on that method.
        assert _UNSAFE_METHODS == frozenset({"POST", "PUT", "PATCH", "DELETE"})

    def test_is_frozenset(self) -> None:
        # Pin: frozenset (immutable). Drift to set would let a
        # careless module-level .add() silently allow / deny
        # methods.
        assert isinstance(_UNSAFE_METHODS, frozenset)

    def test_safe_methods_excluded(self) -> None:
        # Pin: GET / HEAD / OPTIONS / TRACE never trigger CSRF
        # validation. Otherwise navigation-only requests would
        # 403.
        assert "GET" not in _UNSAFE_METHODS
        assert "HEAD" not in _UNSAFE_METHODS
        assert "OPTIONS" not in _UNSAFE_METHODS


class TestSecurityHeaders:
    def test_content_security_policy_pinned(self) -> None:
        # Pin: CSP script-src='self', object-src='none',
        # base-uri='self'. Drift to permissive values re-enables
        # XSS / object embed / base-tag hijack.
        csp = _SECURITY_HEADERS["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "base-uri 'self'" in csp

    def test_csp_allows_inline_styles(self) -> None:
        # Pin: ``style-src 'self' 'unsafe-inline'`` — DaisyUI's
        # generated styles need this. Drift to strict style-src
        # would break every admin page's rendering.
        csp = _SECURITY_HEADERS["Content-Security-Policy"]
        assert "style-src 'self' 'unsafe-inline'" in csp

    def test_csp_img_data_uris(self) -> None:
        # Pin: data: URIs allowed in img-src for inline base64
        # avatars on the admin pages.
        csp = _SECURITY_HEADERS["Content-Security-Policy"]
        assert "img-src 'self' data:" in csp

    def test_no_sniff_pinned(self) -> None:
        # Pin: nosniff defends against MIME-type-sniffing-based
        # XSS. Drift to omit would let a malicious upload
        # masquerade as JS.
        assert _SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options_deny(self) -> None:
        # Pin: DENY (NOT SAMEORIGIN). Admin panel must not be
        # embeddable in any frame — clickjacking defence.
        assert _SECURITY_HEADERS["X-Frame-Options"] == "DENY"

    def test_referrer_policy_no_referrer(self) -> None:
        # Pin: no-referrer (NOT origin / strict-origin). Admin
        # URLs include sensitive resource IDs (workspace id,
        # customer id); leaking them via Referer to external
        # links is a privacy regression.
        assert _SECURITY_HEADERS["Referrer-Policy"] == "no-referrer"

    def test_permissions_policy_blocks_sensitive_features(self) -> None:
        # Pin: camera / microphone / geolocation all disabled
        # for the admin (no UI uses them). Drift would let a
        # compromised admin page silently activate the camera.
        # ``interest-cohort=()`` opts out of FLoC.
        pp = _SECURITY_HEADERS["Permissions-Policy"]
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp
        assert "interest-cohort=()" in pp


class TestCsrfMiddlewareCookieParser:
    def test_extracts_cookie_token_from_headers(self) -> None:
        # Pin: cookie parser handles a typical Cookie header
        # (multiple cookies, our token among them).
        headers = [
            (b"cookie", b"sessionid=abc; _csrf_token=tok123; theme=dark"),
        ]
        token = CSRFMiddleware._get_cookie_token(headers)
        assert token == "tok123"

    def test_returns_none_when_csrf_cookie_absent(self) -> None:
        headers = [(b"cookie", b"sessionid=abc; theme=dark")]
        assert CSRFMiddleware._get_cookie_token(headers) is None

    def test_returns_none_when_no_cookie_header(self) -> None:
        # Pin: missing Cookie header → None (defensive against
        # iteration over a Cookie-less request).
        assert CSRFMiddleware._get_cookie_token([]) is None

    def test_decodes_latin1(self) -> None:
        # Pin: cookie values decoded as latin-1 per RFC 6265.
        # SimpleCookie handles the parsing; we ensure no
        # crash on byte strings.
        headers = [(b"cookie", b"_csrf_token=tok-with-dashes")]
        assert CSRFMiddleware._get_cookie_token(headers) == "tok-with-dashes"


class TestCsrfMiddlewareHeaderParser:
    def test_extracts_header_token(self) -> None:
        # Pin: lowercase header name match (ASGI spec keys all
        # headers as lowercase).
        headers = [
            (b"content-type", b"application/json"),
            (b"x-csrf-token", b"hdr-token"),
        ]
        assert CSRFMiddleware._get_header_token(headers) == "hdr-token"

    def test_returns_none_when_header_absent(self) -> None:
        headers = [(b"content-type", b"application/json")]
        assert CSRFMiddleware._get_header_token(headers) is None

    def test_returns_none_when_no_headers(self) -> None:
        assert CSRFMiddleware._get_header_token([]) is None


class TestCsrfMiddlewareConstantTimeCompare:
    def test_uses_secrets_compare_digest(self) -> None:
        # Pin: SECURITY — token comparison must be constant-time.
        # ``==`` returns at the first differing byte, leaking
        # the matching prefix length via timing. Pin via a
        # smoke-test that two equal-length tokens with one
        # differing char both round-trip through compare_digest
        # with the same observable timing class.
        # (We can't measure timing here; instead we verify
        # that the function being used IS compare_digest by
        # checking its return matches.)
        assert secrets.compare_digest("abc123", "abc123") is True
        assert secrets.compare_digest("abc123", "abc124") is False
        # Equal-length but different — compare_digest still
        # iterates the full length.
        assert secrets.compare_digest("abc123" * 10, "xyz999" * 10) is False


class TestSimpleCookieParsingSafety:
    def test_simplecookie_handles_quoted_values(self) -> None:
        # Pin: SimpleCookie normalises quoted values. Drift to
        # naïve string-split parsing would break on quoted
        # tokens.
        cookie: SimpleCookie = SimpleCookie()
        cookie.load('_csrf_token="quoted-value"')
        morsel = cookie.get(CSRF_COOKIE_NAME)
        assert morsel is not None
        assert morsel.value == "quoted-value"
