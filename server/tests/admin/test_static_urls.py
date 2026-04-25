"""Tests for ``rapidly/admin/static_urls.py``.

Three load-bearing surfaces:

- ``_VERSIONABLE_EXTENSIONS`` is exactly ``(".css", ".js")``. Drift
  to add image extensions would needlessly invalidate the image
  cache on every deploy; drift to drop ``.css`` would let
  stylesheets go stale forever in user browsers.
- For a versionable path, the resolver locates the
  ``VersionedStaticFiles`` app mounted at ``/static`` and appends
  ``?v=<file_version>`` to the URL. Drift to skip the lookup would
  defeat cache busting on legit deploys.
- For a non-versionable path (or when the mount cannot be found /
  is the wrong type), the bare ``url_for`` URL is returned with no
  query string. Drift to fall back to ``?v=`` would emit an empty
  cache-key on some CDNs.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from rapidly.admin import static_urls as M
from rapidly.admin.static_urls import _VERSIONABLE_EXTENSIONS, static_url
from rapidly.admin.versioned_static import VersionedStaticFiles


def _make_request(routes: list[object], url: str = "/static/app.css") -> MagicMock:
    """Build a fake ``Request`` whose ``url_for`` returns ``url`` and whose
    ``app.routes`` iterable yields the supplied routes."""
    request = MagicMock()
    request.url_for.return_value = url
    request.app.routes = routes
    return request


class TestVersionableExtensions:
    def test_pinned_to_css_and_js(self) -> None:
        # Pin: only CSS + JS are cache-busted. Drift to add image
        # extensions would burn the image cache on every deploy;
        # drift to drop ``.css`` would let stylesheets go stale.
        assert _VERSIONABLE_EXTENSIONS == (".css", ".js")


class TestStaticUrlVersionable:
    def test_appends_version_query_for_css(self) -> None:
        # Pin: ``.css`` paths get ``?v=<hash>`` appended once the
        # resolver finds the VersionedStaticFiles mount at
        # ``/static``.
        versioned_app = MagicMock(spec=VersionedStaticFiles)
        versioned_app.get_file_version.return_value = "abcd1234"
        route = SimpleNamespace(path="/static", app=versioned_app)
        request = _make_request([route], url="/static/app.css")

        result = static_url(request, "app.css")

        assert result == "/static/app.css?v=abcd1234"
        versioned_app.get_file_version.assert_called_once_with("app.css")

    def test_appends_version_query_for_js(self) -> None:
        # Pin: same behaviour for ``.js`` paths.
        versioned_app = MagicMock(spec=VersionedStaticFiles)
        versioned_app.get_file_version.return_value = "deadbeef"
        route = SimpleNamespace(path="/static", app=versioned_app)
        request = _make_request([route], url="/static/main.js")

        result = static_url(request, "main.js")

        assert result == "/static/main.js?v=deadbeef"

    def test_skips_non_versionable_extension(self) -> None:
        # Pin: non-CSS/JS files (here ``.png``) get the bare URL
        # back with no query parameter -- and the resolver does
        # NOT even need to look up the mount.
        versioned_app = MagicMock(spec=VersionedStaticFiles)
        route = SimpleNamespace(path="/static", app=versioned_app)
        request = _make_request([route], url="/static/logo.png")

        result = static_url(request, "logo.png")

        assert result == "/static/logo.png"
        versioned_app.get_file_version.assert_not_called()


class TestStaticUrlMountFallback:
    def test_returns_base_url_when_mount_missing(self) -> None:
        # Pin: when the ``/static`` mount cannot be found at all
        # (defensive path), the bare URL is returned with no
        # query. Drift to emit ``?v=`` would create an empty
        # cache-key on some CDNs.
        request = _make_request([], url="/static/app.css")
        assert static_url(request, "app.css") == "/static/app.css"

    def test_returns_base_url_when_mount_is_wrong_type(self) -> None:
        # Pin: a route at ``/static`` that is NOT a
        # VersionedStaticFiles instance is rejected (the loop
        # ``break``s without appending). This pins the
        # ``isinstance`` guard.
        not_versioned = SimpleNamespace(get_file_version=lambda _: "ignored")
        route = SimpleNamespace(path="/static", app=not_versioned)
        request = _make_request([route], url="/static/app.css")

        assert static_url(request, "app.css") == "/static/app.css"

    def test_skips_routes_with_other_paths(self) -> None:
        # Pin: only ``/static`` matches. Other-path routes are
        # ignored, so a versionable file falls through to the
        # bare URL when the right mount is absent.
        decoy = SimpleNamespace(path="/api", app=MagicMock(spec=VersionedStaticFiles))
        request = _make_request([decoy], url="/static/app.css")

        assert static_url(request, "app.css") == "/static/app.css"


class TestModuleSurface:
    def test_static_url_is_exported(self) -> None:
        # Pin: the function is callable from the module namespace
        # (Jinja2 imports it by name into the template globals).
        assert callable(M.static_url)
