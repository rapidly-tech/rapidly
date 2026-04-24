"""Tests for ``rapidly/admin/responses.py``.

Two security-sensitive helpers:

- ``validate_redirect_url`` — the admin panel's open-redirect defence.
  The admin UI has `?next=` / form-submission redirects; unvalidated
  URLs would let an attacker craft a dashboard link that bounces the
  admin through an attacker-controlled origin.
- ``HXRedirectResponse`` — redirects that cooperate with HTMX. The
  URL passes through the validator AND switches between a standard
  3xx (normal request) and 200 + ``HX-Redirect`` header (HTMX
  request) so the browser URL bar updates correctly.

Also pins that ``TagResponse`` defers rendering to ``__call__`` so
toast accumulation during the handler can still write into the
response body.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from rapidly.admin.responses import (
    HXRedirectResponse,
    TagResponse,
    validate_redirect_url,
)


class TestValidateRedirectUrl:
    def test_allows_relative_paths(self) -> None:
        assert validate_redirect_url("/admin/workspaces") == "/admin/workspaces"

    def test_allows_bare_paths(self) -> None:
        assert validate_redirect_url("settings") == "settings"

    def test_allows_query_only(self) -> None:
        assert validate_redirect_url("?tab=users") == "?tab=users"

    def test_allows_configured_frontend_host(self) -> None:
        # ``http://127.0.0.1:3000`` is FRONTEND_BASE_URL — must pass.
        url = "http://127.0.0.1:3000/dashboard"
        assert validate_redirect_url(url) == url

    def test_allows_configured_api_host(self) -> None:
        # ``http://127.0.0.1:8000`` is BASE_URL — must pass.
        url = "http://127.0.0.1:8000/admin/"
        assert validate_redirect_url(url) == url

    def test_rejects_unknown_host(self) -> None:
        # Load-bearing security pin. ``https://evil.test/steal`` must
        # NOT pass — that would be an open-redirect.
        with pytest.raises(ValueError, match="disallowed host"):
            validate_redirect_url("https://evil.test/steal")

    @pytest.mark.parametrize(
        "hostile",
        [
            "javascript:alert(1)",
            "data:text/html,<script>",
            "file:///etc/passwd",
            "ftp://example.com/",
        ],
    )
    def test_rejects_non_http_schemes(self, hostile: str) -> None:
        with pytest.raises(ValueError, match="disallowed"):
            validate_redirect_url(hostile)

    def test_allowed_hostname_without_port_is_accepted(self) -> None:
        # ``ALLOWED_HOSTS`` stores ``host:port`` pairs; the validator
        # falls back to hostname-only comparison so a bare hostname
        # (no port) matches too — useful for dev environments where
        # port forwarding varies.
        assert (
            validate_redirect_url("http://127.0.0.1/some/path")
            == "http://127.0.0.1/some/path"
        )


class TestHXRedirectResponse:
    def _req(self, hx: bool = False) -> Any:
        req = MagicMock()
        req.headers = {"HX-Request": "true"} if hx else {}
        return req

    def test_standard_request_uses_3xx_with_location(self) -> None:
        resp = HXRedirectResponse(self._req(), "/admin/workspaces")
        # RedirectResponse sets status_code to the effective_status
        # and a Location header.
        assert resp.status_code == 307
        assert resp.headers["location"] == "/admin/workspaces"
        assert "HX-Redirect" not in resp.headers

    def test_htmx_request_returns_200_with_hx_redirect(self) -> None:
        # Load-bearing HTMX-compat pin. HTMX intercepts 3xx redirects
        # silently at the XHR layer — the browser URL bar does NOT
        # update. Serving 200 + ``HX-Redirect`` header lets HTMX
        # trigger a full navigation.
        resp = HXRedirectResponse(self._req(hx=True), "/admin/workspaces")
        assert resp.status_code == 200
        assert resp.headers["HX-Redirect"] == "/admin/workspaces"

    def test_validates_url_before_redirecting(self) -> None:
        with pytest.raises(ValueError, match="disallowed"):
            HXRedirectResponse(self._req(), "https://evil.test/steal")

    def test_non_307_status_respected_on_standard_request(self) -> None:
        resp = HXRedirectResponse(self._req(), "/admin/workspaces", status_code=302)
        assert resp.status_code == 302

    def test_htmx_request_forces_200_regardless_of_status_code(self) -> None:
        # Even if the caller asked for ``status_code=301``, an HTMX
        # request MUST get 200 — otherwise HTMX would follow the
        # redirect silently.
        resp = HXRedirectResponse(
            self._req(hx=True), "/admin/workspaces", status_code=301
        )
        assert resp.status_code == 200


class TestTagResponseDeferredRender:
    def test_content_is_captured_in_init_not_rendered(self) -> None:
        # ``TagResponse.__init__`` stores ``self.content`` but does
        # NOT call ``self.render(...)``. Pinning prevents a
        # regression that eager-renders and misses toasts added
        # post-init.
        sentinel = MagicMock()
        resp = TagResponse(content=sentinel)
        assert resp.content is sentinel
        # The body is only computed in __call__, not here.
        assert getattr(resp, "body", None) in (None, b"", ...)

    def test_accepts_status_and_headers_kwargs(self) -> None:
        resp = TagResponse(
            content=MagicMock(),
            status_code=201,
            headers={"X-Custom": "value"},
        )
        assert resp.status_code == 201
        assert resp.headers["X-Custom"] == "value"
