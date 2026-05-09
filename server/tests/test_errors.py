"""Tests for ``rapidly/errors/__init__.py``.

The Rapidly exception hierarchy. Every leaf exception maps to a
single HTTP status code + machine-readable ``ErrorCode``. Both
pairs are client-facing — SDKs pattern-match on the code string
to render the right UI for each failure mode.

Pins:
- Each leaf's default ``status_code`` + ``code`` pair
- ``Unauthorized`` sets the documented ``WWW-Authenticate`` header
  with the configured realm (RFC 6750 compat)
- ``RedirectionError`` surfaces ``return_to`` for the /error view
  to round-trip the caller
- ``schema()`` memoises and builds a Pydantic model named after the
  leaf class (used in OpenAPI error responses)
- ``validation_error`` helper builds the canonical dict the
  ``RequestValidationError`` consumes
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from rapidly.config import settings
from rapidly.errors import (
    BackgroundTaskError,
    BadRequest,
    ErrorCode,
    FileScanFailed,
    InternalServerError,
    NotPermitted,
    PaymentNotReady,
    QuotaExceeded,
    RapidlyError,
    RedirectionError,
    RequestValidationError,
    ResourceAlreadyExists,
    ResourceNotFound,
    ShareExpired,
    Unauthorized,
    validation_error,
)


class TestErrorCodeEnum:
    def test_has_exactly_twelve_codes(self) -> None:
        # Pinning the arity prevents a silent addition that the SDK
        # doesn't yet handle.
        assert len(list(ErrorCode)) == 12

    def test_known_wire_values(self) -> None:
        # Wire values are SDK-facing — pattern matching on these
        # literals drives the error-rendering UX.
        assert ErrorCode.BAD_REQUEST == "BAD_REQUEST"
        assert ErrorCode.UNAUTHORIZED == "UNAUTHORIZED"
        assert ErrorCode.FORBIDDEN == "FORBIDDEN"
        assert ErrorCode.NOT_FOUND == "NOT_FOUND"
        assert ErrorCode.CONFLICT == "CONFLICT"
        assert ErrorCode.GONE == "GONE"
        assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"


class TestLeafStatusAndCode:
    @pytest.mark.parametrize(
        ("exc_cls", "status", "code"),
        [
            (BadRequest, 400, ErrorCode.BAD_REQUEST),
            (NotPermitted, 403, ErrorCode.FORBIDDEN),
            (PaymentNotReady, 403, ErrorCode.PAYMENT_NOT_READY),
            (ResourceNotFound, 404, ErrorCode.NOT_FOUND),
            (ResourceAlreadyExists, 409, ErrorCode.CONFLICT),
            (ShareExpired, 410, ErrorCode.SHARE_EXPIRED),
            (FileScanFailed, 422, ErrorCode.FILE_SCAN_FAILED),
            (QuotaExceeded, 429, ErrorCode.QUOTA_EXCEEDED),
            (InternalServerError, 500, ErrorCode.INTERNAL_ERROR),
        ],
    )
    def test_defaults_pinned(
        self,
        exc_cls: type[RapidlyError],
        status: int,
        code: ErrorCode,
    ) -> None:
        # Each leaf class defaults ``message`` in its own ctor; the
        # mypy view of the base RapidlyError insists on it, so the
        # call is routed via a cast that preserves the callable shape.
        from typing import cast

        err = cast("type", exc_cls)()
        assert err.status_code == status
        assert err.code == code


class TestUnauthorizedHeaders:
    def test_sets_www_authenticate_with_realm(self) -> None:
        # RFC 6750 — Unauthorized responses must carry the
        # ``WWW-Authenticate: Bearer realm="..."`` header; strict
        # OAuth2 clients refuse unrealmed 401s.
        err = Unauthorized()
        assert err.headers is not None
        auth_header = err.headers.get("WWW-Authenticate")
        assert auth_header is not None
        assert f'realm="{settings.WWW_AUTHENTICATE_REALM}"' in auth_header
        assert auth_header.startswith("Bearer ")

    def test_status_and_code(self) -> None:
        err = Unauthorized()
        assert err.status_code == 401
        assert err.code == ErrorCode.UNAUTHORIZED


class TestRedirectionError:
    def test_preserves_return_to(self) -> None:
        # ``return_to`` round-trips through the /error frontend view
        # so the user lands back where they came from after seeing
        # the error message.
        err = RedirectionError("something went wrong", return_to="/dashboard")
        assert err.return_to == "/dashboard"
        assert err.status_code == 400
        assert err.code == ErrorCode.BAD_REQUEST

    def test_default_return_to_is_none(self) -> None:
        err = RedirectionError("x")
        assert err.return_to is None


class TestBackgroundTaskError:
    def test_never_carries_http_translation(self) -> None:
        # Worker errors don't reach the HTTP layer, but they still
        # inherit from RapidlyError for consistent logging. Code
        # maps to INTERNAL_ERROR; no explicit status_code override.
        err = BackgroundTaskError("task failed")
        assert err.code == ErrorCode.INTERNAL_ERROR
        assert str(err) == "task failed"


class TestSchemaGeneration:
    def test_returns_pydantic_model_named_after_class(self) -> None:
        # ``schema()`` is used in the OpenAPI error-response table;
        # the model's name must be the leaf-class name so SDKs
        # generate the right TypeScript type.
        schema = ResourceNotFound.schema()
        assert issubclass(schema, BaseModel)
        assert schema.__name__ == "ResourceNotFound"

    def test_memoised(self) -> None:
        # Generating the Pydantic model on every access would blow
        # per-request latency. Pinning identity ensures ``schema()``
        # caches the first build.
        a = BadRequest.schema()
        b = BadRequest.schema()
        assert a is b

    def test_each_leaf_gets_distinct_schema(self) -> None:
        # Different leaves must produce distinct models so the
        # OpenAPI error table doesn't collapse them into one shape.
        assert ResourceNotFound.schema() is not BadRequest.schema()


class TestValidationErrorHelper:
    def test_builds_canonical_dict(self) -> None:
        ve = validation_error("email", "must not be empty", "")
        assert ve == {
            "type": "value_error",
            "loc": ("body", "email"),
            "msg": "must not be empty",
            "input": "",
        }

    def test_custom_loc_prefix(self) -> None:
        # Query-string / header validation errors need the right
        # ``loc_prefix`` so the SDK can render the error next to
        # the right input.
        ve = validation_error("page", "must be positive", 0, loc_prefix="query")
        assert ve["loc"] == ("query", "page")


class TestRequestValidationError:
    def test_is_a_rapidly_error(self) -> None:
        err = RequestValidationError([validation_error("email", "bad", "")])
        assert isinstance(err, RapidlyError)

    def test_errors_produces_pydantic_format(self) -> None:
        # The handler reads ``.errors()`` to build the 422 response.
        # Pin the shape so a refactor that returned raw dicts
        # instead of Pydantic ErrorDetails would surface here.
        err = RequestValidationError([validation_error("email", "bad", "")])
        errors = err.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("body", "email")


class TestExports:
    def test_major_exports_present(self) -> None:
        from rapidly import errors as E

        # Spot check — the full 14-entry __all__ is the module's
        # public API.
        for name in (
            "RapidlyError",
            "ErrorCode",
            "BadRequest",
            "Unauthorized",
            "NotPermitted",
            "ResourceNotFound",
            "ResourceAlreadyExists",
            "ShareExpired",
            "FileScanFailed",
            "QuotaExceeded",
            "InternalServerError",
            "RequestValidationError",
        ):
            assert name in E.__all__
