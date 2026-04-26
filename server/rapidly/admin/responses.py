"""HTTP response helpers for the Rapidly admin panel.

``TagResponse``
    A tagflow-aware response that defers HTML rendering until send-time
    so that toast notifications accumulated during the request are
    included in the output.

``HXRedirectResponse``
    A redirect that works transparently for both standard and HTMX
    requests by setting the ``HX-Redirect`` header when needed.
"""

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from fastapi.datastructures import URL
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from starlette.background import BackgroundTask
from starlette.types import Receive, Scope, Send
from tagflow import TagResponse as _TagResponse

from rapidly.config import settings

from .toast import render_toasts


def validate_redirect_url(url: str) -> str:
    """Ensure a redirect URL is relative or points to an allowed host.

    Raises ``ValueError`` for absolute URLs targeting unknown hosts,
    preventing open-redirect attacks via user-controlled path or query
    parameters.
    """
    parsed = urlparse(url)
    if parsed.netloc:
        # Build allow-list from both ALLOWED_HOSTS (host:port pairs) and
        # the configured base URLs.  Check against both netloc and hostname
        # so that port-qualified entries in ALLOWED_HOSTS match correctly.
        allowed_netlocs = settings.ALLOWED_HOSTS | {
            urlparse(settings.FRONTEND_BASE_URL).netloc,
            urlparse(settings.BASE_URL).netloc,
        }
        allowed_hostnames = {h.split(":")[0] for h in allowed_netlocs}
        if (
            parsed.netloc not in allowed_netlocs
            and parsed.hostname not in allowed_hostnames
        ):
            raise ValueError(f"Redirect to disallowed host: {parsed.netloc}")
    if parsed.scheme and parsed.scheme not in ("http", "https", ""):
        raise ValueError(f"Redirect with disallowed scheme: {parsed.scheme}")
    return url


class TagResponse(_TagResponse):
    """Tagflow response that renders *after* the ASGI scope is available.

    Standard ``TagResponse`` renders eagerly in ``__init__``.  We need to
    delay rendering so the toast container (which reads ``scope["toasts"]``)
    can include any messages added during request handling.
    """

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        self.status_code = status_code
        if media_type is not None:
            self.media_type = media_type
        self.background = background
        self.content = content
        self._initial_headers = headers
        self.init_headers(headers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Flush accumulated toasts into the HTML tree before rendering.
        with render_toasts(scope):
            pass
        self.body = self.render(self.content)
        self.init_headers(self._initial_headers)
        await super().__call__(scope, receive, send)


class HXRedirectResponse(RedirectResponse):
    """Redirect that cooperates with HTMX's client-side router.

    When the incoming request carries ``HX-Request: true``, a standard
    3xx redirect would be followed silently by the XMLHttpRequest layer
    and the browser URL bar would not update.  Instead we return a 200
    with an ``HX-Redirect`` header so htmx performs a full navigation.

    The target URL is validated against the configured allow-list to
    prevent open-redirect attacks.
    """

    def __init__(
        self,
        request: Request,
        url: str | URL,
        status_code: int = 307,
        headers: dict[str, str] | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        validated_url = validate_redirect_url(str(url))
        htmx_request = request.headers.get("HX-Request") == "true"
        effective_status = 200 if htmx_request else status_code
        super().__init__(validated_url, effective_status, headers, background)
        if htmx_request:
            self.headers["HX-Redirect"] = self.headers["location"]
