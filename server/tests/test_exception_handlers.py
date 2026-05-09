"""Tests for ``rapidly/exception_handlers.py``.

The handlers translate domain exceptions to HTTP responses. Three
load-bearing surfaces:

- ``_handle_app_error`` preserves the exception's ``headers`` —
  ``Unauthorized`` sets ``WWW-Authenticate``; dropping it would
  break OAuth2 clients that need the realm to retry
- ``_handle_redirection_error`` passes ``message`` AND ``return_to``
  through the redirect query string so the frontend ``/error`` view
  can render the message + return the user to where they came from
- ``_HANDLER_REGISTRY`` lists leaf types BEFORE their base
  (``RedirectionError`` before ``RapidlyError``); a regression
  reordering would let the broad handler swallow a redirect.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.exceptions import RequestValidationError as FastAPIValidationError
from fastapi.responses import RedirectResponse

from rapidly.errors import (
    BadRequest,
    RapidlyError,
    RedirectionError,
    Unauthorized,
    validation_error,
)
from rapidly.errors import RequestValidationError as AppValidationError
from rapidly.exception_handlers import (
    _HANDLER_REGISTRY,
    _handle_app_error,
    _handle_redirection_error,
    _handle_validation_error,
    add_exception_handlers,
)


@pytest.mark.asyncio
class TestHandleAppError:
    async def test_response_shape(self) -> None:
        # ``error`` is the exception class name; ``detail`` is the
        # message. SDKs dispatch on the class name string.
        err = BadRequest("invalid foo")
        response = await _handle_app_error(MagicMock(), err)
        assert response.status_code == 400
        body = json.loads(response.body)
        assert body == {"error": "BadRequest", "detail": "invalid foo"}

    async def test_preserves_headers(self) -> None:
        # Load-bearing pin. ``Unauthorized`` carries
        # ``WWW-Authenticate: Bearer realm="..."`` — dropping it
        # breaks strict OAuth2 clients that retry on realm.
        err = Unauthorized()
        response = await _handle_app_error(MagicMock(), err)
        assert response.headers.get("WWW-Authenticate") is not None
        assert "Bearer realm" in response.headers["WWW-Authenticate"]

    async def test_status_code_from_exception(self) -> None:
        # Custom status code on a generic RapidlyError flows through.
        err = RapidlyError("boom", status_code=418)
        response = await _handle_app_error(MagicMock(), err)
        assert response.status_code == 418


@pytest.mark.asyncio
class TestHandleValidationError:
    async def test_app_validation_error_normalised(self) -> None:
        # ``RequestValidationError`` is the in-house wrapper; its
        # ``.errors()`` returns Pydantic ErrorDetails that the
        # handler must JSON-encode under ``detail``.
        err = AppValidationError([validation_error("email", "must not be empty", "")])
        response = await _handle_validation_error(MagicMock(), err)
        assert response.status_code == 422
        body = json.loads(response.body)
        assert body["error"] == "RequestValidationError"
        assert isinstance(body["detail"], list)
        assert len(body["detail"]) == 1
        assert body["detail"][0]["loc"] == ["body", "email"]

    async def test_fastapi_validation_error_normalised_into_same_shape(
        self,
    ) -> None:
        # The same handler must work for FastAPI's framework-emitted
        # validation errors so SDKs see ONE 422 shape regardless of
        # whether the error came from Pydantic or our custom code.
        err = FastAPIValidationError([])
        response = await _handle_validation_error(MagicMock(), err)
        assert response.status_code == 422
        body = json.loads(response.body)
        # error name comes from ``type(exc).__name__``; both
        # variants flow through the same shape.
        assert body["error"] == "RequestValidationError"
        assert body["detail"] == []


@pytest.mark.asyncio
class TestHandleRedirectionError:
    async def test_returns_303_redirect_to_frontend_error_view(self) -> None:
        from rapidly.config import settings

        err = RedirectionError("OAuth callback failed", return_to="/dashboard")
        response = await _handle_redirection_error(MagicMock(), err)
        assert isinstance(response, RedirectResponse)
        assert response.status_code == 303
        # Location ends with /error?...
        location = response.headers["location"]
        parsed = urlparse(location)
        assert location.startswith(settings.FRONTEND_BASE_URL)
        assert parsed.path == "/error"
        params = parse_qs(parsed.query)
        assert params["message"] == ["OAuth callback failed"]
        assert params["return_to"] == ["/dashboard"]

    async def test_falls_back_to_default_return_path(self) -> None:
        # When ``return_to`` is None, the helper must still pass a
        # value so the frontend's redirect after the error display
        # has somewhere to go.
        from rapidly.config import settings

        err = RedirectionError("boom", return_to=None)
        response = await _handle_redirection_error(MagicMock(), err)
        location = response.headers["location"]
        params = parse_qs(urlparse(location).query)
        assert params["return_to"] == [settings.FRONTEND_DEFAULT_RETURN_PATH]


class TestHandlerRegistry:
    def test_leaf_types_precede_their_parents(self) -> None:
        # Load-bearing pin. ``RedirectionError`` is a subclass of
        # ``RapidlyError``; FastAPI's exception dispatch picks the
        # FIRST handler that matches, so the leaf type MUST be
        # registered before its base. A regression reordering would
        # let the broad ``RapidlyError`` handler swallow a redirect
        # and return JSON instead of a 303.
        positions = {cls: i for i, (cls, _) in enumerate(_HANDLER_REGISTRY)}
        assert positions[RedirectionError] < positions[RapidlyError]
        assert positions[FastAPIValidationError] < positions[RapidlyError]
        assert positions[AppValidationError] < positions[RapidlyError]

    def test_registry_covers_documented_classes(self) -> None:
        registered = {cls for cls, _ in _HANDLER_REGISTRY}
        assert registered == {
            RedirectionError,
            FastAPIValidationError,
            AppValidationError,
            RapidlyError,
        }


class TestAddExceptionHandlers:
    def test_registers_every_handler(self) -> None:
        # ``add_exception_handlers`` walks the registry and calls
        # ``app.add_exception_handler`` for each entry.
        app = MagicMock()
        registered: list[tuple[type[Exception], Any]] = []
        app.add_exception_handler = lambda cls, handler: registered.append(
            (cls, handler)
        )
        add_exception_handlers(app)
        assert len(registered) == len(_HANDLER_REGISTRY)
        # Order matches the registry — load-bearing for ASGI
        # dispatch precedence.
        for got, expected in zip(registered, _HANDLER_REGISTRY, strict=True):
            assert got == expected
