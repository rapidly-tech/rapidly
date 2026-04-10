"""Map domain exceptions to HTTP responses.

Each exception class is paired with a handler via the ``_HANDLER_REGISTRY``
mapping.  The ``add_exception_handlers`` function iterates over the registry
and registers them on the FastAPI app in precedence order (most-specific
exception types first).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError as FastAPIValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response

from rapidly.config import settings
from rapidly.errors import (
    RapidlyError,
    RedirectionError,
)
from rapidly.errors import (
    RequestValidationError as AppValidationError,
)

# Type alias for exception handler callables
type _Handler = Callable[[Request, Any], Awaitable[Response]]


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------


async def _handle_app_error(request: Request, exc: RapidlyError) -> JSONResponse:
    """Fallback handler that wraps any domain exception in a JSON error body."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": type(exc).__name__, "detail": exc.message},
        headers=exc.headers,
    )


async def _handle_validation_error(
    request: Request, exc: FastAPIValidationError | AppValidationError
) -> JSONResponse:
    """Normalise both framework-generated and custom validation errors into a single 422 shape."""
    return JSONResponse(
        status_code=422,
        content={
            "error": type(exc).__name__,
            "detail": jsonable_encoder(exc.errors()),
        },
    )


async def _handle_redirection_error(
    request: Request, exc: RedirectionError
) -> RedirectResponse:
    """Send the browser to the frontend ``/error`` view, passing along the error details."""
    destination = settings.generate_frontend_url("/error")
    params = urlencode(
        {
            "message": exc.message,
            "return_to": exc.return_to or settings.FRONTEND_DEFAULT_RETURN_PATH,
        }
    )
    return RedirectResponse(f"{destination}?{params}", status_code=303)


# ---------------------------------------------------------------------------
# Handler registry -- order defines registration precedence.
# Leaf types MUST precede their parents so the ASGI dispatch picks the
# narrowest match.
# ---------------------------------------------------------------------------

_HANDLER_REGISTRY: list[tuple[type[Exception], _Handler]] = [
    (RedirectionError, _handle_redirection_error),
    (FastAPIValidationError, _handle_validation_error),
    (AppValidationError, _handle_validation_error),
    (RapidlyError, _handle_app_error),
]


def add_exception_handlers(app: FastAPI) -> None:
    """Walk the handler registry and attach each entry to *app*."""
    for exc_cls, handler in _HANDLER_REGISTRY:
        app.add_exception_handler(exc_cls, handler)
