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

from fastapi.datastructures import URL
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from starlette.background import BackgroundTask
from starlette.types import Receive, Scope, Send
from tagflow import TagResponse as _TagResponse

from .toast import render_toasts


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
    """

    def __init__(
        self,
        request: Request,
        url: str | URL,
        status_code: int = 307,
        headers: dict[str, str] | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        htmx_request = request.headers.get("HX-Request") == "true"
        effective_status = 200 if htmx_request else status_code
        super().__init__(url, effective_status, headers, background)
        if htmx_request:
            self.headers["HX-Redirect"] = self.headers["location"]
