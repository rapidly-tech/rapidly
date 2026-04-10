"""Admin panel-specific ASGI middlewares."""

import functools
import secrets
from http.cookies import SimpleCookie

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from tagflow import document

# ---------------------------------------------------------------------------
# CSRF cookie name and header
# ---------------------------------------------------------------------------

CSRF_COOKIE_NAME = "_csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"

# HTTP methods that require CSRF validation (state-changing).
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
}


class TagflowMiddleware:
    __slots__ = ("app",)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        with document():
            await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    __slots__ = ("app",)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        await self.app(scope, receive, functools.partial(self._inject, send=send))

    @staticmethod
    async def _inject(message: Message, send: Send) -> None:
        if message["type"] == "http.response.start":
            message.setdefault("headers", [])
            headers = MutableHeaders(scope=message)
            for name, value in _SECURITY_HEADERS.items():
                headers[name] = value
        await send(message)


class CSRFMiddleware:
    """Double-submit cookie CSRF protection for admin panel routes.

    On every response a ``_csrf_token`` cookie is set (or refreshed) with
    ``SameSite=Strict`` and ``HttpOnly=False`` so that client-side JS
    (HTMX) can read it.

    For state-changing methods (POST / PUT / PATCH / DELETE) the
    middleware requires an ``X-CSRF-Token`` header whose value matches the
    cookie.  Requests without a valid match receive a 403 response.
    """

    __slots__ = ("app",)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method: str = scope.get("method", "GET")
        headers_raw: list[tuple[bytes, bytes]] = scope.get("headers", [])

        # Parse the CSRF cookie from the request.
        cookie_token = self._get_cookie_token(headers_raw)

        if method in _UNSAFE_METHODS:
            header_token = self._get_header_token(headers_raw)
            if (
                not cookie_token
                or not header_token
                or not secrets.compare_digest(cookie_token, header_token)
            ):
                await self._send_403(send)
                return

        # Ensure the cookie is present on every response.  Generate a new
        # token when no valid one exists yet.
        token = cookie_token or secrets.token_urlsafe(32)

        # Store the token on the scope so the base template can read it.
        scope["csrf_token"] = token

        await self.app(
            scope,
            receive,
            functools.partial(self._inject_cookie, send=send, token=token),
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _get_cookie_token(headers: list[tuple[bytes, bytes]]) -> str | None:
        for key, value in headers:
            if key == b"cookie":
                cookie: SimpleCookie = SimpleCookie()
                cookie.load(value.decode("latin-1"))
                morsel = cookie.get(CSRF_COOKIE_NAME)
                if morsel is not None:
                    return morsel.value
        return None

    @staticmethod
    def _get_header_token(headers: list[tuple[bytes, bytes]]) -> str | None:
        for key, value in headers:
            if key == CSRF_HEADER_NAME.encode():
                return value.decode("latin-1")
        return None

    @staticmethod
    async def _send_403(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"CSRF token missing or invalid",
            }
        )

    @staticmethod
    async def _inject_cookie(message: Message, send: Send, token: str) -> None:
        if message["type"] == "http.response.start":
            message.setdefault("headers", [])
            headers = MutableHeaders(scope=message)
            headers.append(
                "set-cookie",
                (f"{CSRF_COOKIE_NAME}={token}; Path=/; SameSite=Strict; Secure"),
            )
        await send(message)
