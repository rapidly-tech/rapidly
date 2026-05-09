"""URL resolver for versioned static assets in Jinja2 templates.

Exposes a single ``static_url`` helper that appends a content-hash query
parameter to CSS and JavaScript paths so that browser caches are busted
automatically on deploy.
"""

from __future__ import annotations

from fastapi import Request

from .versioned_static import VersionedStaticFiles

_VERSIONABLE_EXTENSIONS: tuple[str, ...] = (".css", ".js")


def static_url(request: Request, path: str) -> str:
    """Build a URL to a static file, appending ``?v=<hash>`` for CSS/JS.

    Non-versionable file types are returned without a query parameter.
    """
    base_url: str = str(request.url_for("static", path=path))

    if not path.endswith(_VERSIONABLE_EXTENSIONS):
        return base_url

    # Walk the mounted routes to find the VersionedStaticFiles app
    for route in request.app.routes:
        if getattr(route, "path", None) != "/static":
            continue
        if isinstance(route.app, VersionedStaticFiles):
            version = route.app.get_file_version(path)
            return f"{base_url}?v={version}"
        break

    return base_url
