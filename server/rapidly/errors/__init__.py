"""Rapidly exception hierarchy.

Every domain-level exception inherits from ``RapidlyError``, which is caught by
the global handler in ``rapidly.exception_handlers`` and converted to the
appropriate HTTP response.  The hierarchy is intentionally flat — each leaf
class maps to exactly one HTTP status code.

Hierarchy
---------
::

    Exception
    ├── RapidlyError (500)
    │   ├── BackgroundTaskError       — worker tasks, not HTTP
    │   ├── RedirectionError (400)    — redirects to /error
    │   ├── BadRequest (400)
    │   ├── Unauthorized (401)
    │   ├── NotPermitted (403)
    │   ├── PaymentNotReady (403)
    │   ├── ResourceNotFound (404)
    │   ├── ResourceAlreadyExists (409)
    │   ├── FileScanFailed (422)
    │   ├── QuotaExceeded (429)
    │   ├── ShareExpired (410)
    │   ├── InternalServerError (500)
    │   └── RequestValidationError (422)
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, ClassVar, Literal, LiteralString, NotRequired, TypedDict

from pydantic import BaseModel, Field, create_model
from pydantic_core import ErrorDetails, InitErrorDetails, PydanticCustomError
from pydantic_core import ValidationError as PydanticValidationError

from rapidly.config import settings

# Default HTTP status codes — centralised so leaf classes stay concise.
_STATUS_BAD_REQUEST: int = 400
_STATUS_UNAUTHORIZED: int = 401
_STATUS_FORBIDDEN: int = 403
_STATUS_NOT_FOUND: int = 404
_STATUS_CONFLICT: int = 409
_STATUS_GONE: int = 410
_STATUS_UNPROCESSABLE: int = 422
_STATUS_TOO_MANY_REQUESTS: int = 429
_STATUS_INTERNAL: int = 500


# ── Error codes ───────────────────────────────────────────────────────


class ErrorCode(StrEnum):
    """Machine-readable error codes attached to every ``RapidlyError``."""

    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    GONE = "GONE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    FILE_SCAN_FAILED = "FILE_SCAN_FAILED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    SHARE_EXPIRED = "SHARE_EXPIRED"
    PAYMENT_NOT_READY = "PAYMENT_NOT_READY"


# ── Base exception ─────────────────────────────────────────────────────


class RapidlyError(Exception):
    """Base for all Rapidly HTTP errors, caught by the global exception handler."""

    _schema: ClassVar[type[BaseModel] | None] = None

    def __init__(
        self,
        message: str,
        status_code: int = _STATUS_INTERNAL,
        headers: dict[str, str] | None = None,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.headers = headers
        self.code = code

    @classmethod
    def schema(cls) -> type[BaseModel]:
        """Return (or create on first access) a Pydantic model used in OpenAPI error responses."""
        if cls._schema is not None:
            return cls._schema

        error_literal = Literal[cls.__name__]  # type: ignore
        cls._schema = create_model(
            cls.__name__,
            error=(error_literal, Field(examples=[cls.__name__])),
            detail=(str, ...),
        )
        return cls._schema


# ── Worker errors ──────────────────────────────────────────────────────


class BackgroundTaskError(RapidlyError):
    """Used by background workers (Dramatiq); never translated into an HTTP response."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code=ErrorCode.INTERNAL_ERROR)


# ── Redirect errors ───────────────────────────────────────────────────


class RedirectionError(RapidlyError):
    """Sends the caller to the frontend ``/error`` view along with a user-facing explanation."""

    def __init__(
        self,
        message: str,
        status_code: int = _STATUS_BAD_REQUEST,
        return_to: str | None = None,
    ) -> None:
        self.return_to = return_to
        super().__init__(message, status_code, code=ErrorCode.BAD_REQUEST)


# ── Client errors ─────────────────────────────────────────────────────


class BadRequest(RapidlyError):
    def __init__(
        self, message: str = "Bad request", status_code: int = _STATUS_BAD_REQUEST
    ) -> None:
        super().__init__(message, status_code, code=ErrorCode.BAD_REQUEST)


class NotPermitted(RapidlyError):
    def __init__(
        self, message: str = "Not permitted", status_code: int = _STATUS_FORBIDDEN
    ) -> None:
        super().__init__(message, status_code, code=ErrorCode.FORBIDDEN)


class Unauthorized(RapidlyError):
    def __init__(
        self, message: str = "Unauthorized", status_code: int = _STATUS_UNAUTHORIZED
    ) -> None:
        super().__init__(
            message,
            status_code,
            headers={
                "WWW-Authenticate": f'Bearer realm="{settings.WWW_AUTHENTICATE_REALM}"'
            },
            code=ErrorCode.UNAUTHORIZED,
        )


class PaymentNotReady(RapidlyError):
    """The workspace's payout setup is incomplete."""

    def __init__(
        self,
        message: str = "Workspace is not ready to accept payments",
        status_code: int = _STATUS_FORBIDDEN,
    ) -> None:
        super().__init__(message, status_code, code=ErrorCode.PAYMENT_NOT_READY)


# ── Resource errors ────────────────────────────────────────────────────


class ResourceNotFound(RapidlyError):
    def __init__(
        self, message: str = "Not found", status_code: int = _STATUS_NOT_FOUND
    ) -> None:
        super().__init__(message, status_code, code=ErrorCode.NOT_FOUND)


class ResourceAlreadyExists(RapidlyError):
    def __init__(
        self, message: str = "Already exists", status_code: int = _STATUS_CONFLICT
    ) -> None:
        super().__init__(message, status_code, code=ErrorCode.CONFLICT)


# ── File-sharing errors ───────────────────────────────────────────────


class FileScanFailed(RapidlyError):
    """The uploaded file failed a virus/malware scan."""

    def __init__(
        self,
        message: str = "File scan failed",
        status_code: int = _STATUS_UNPROCESSABLE,
    ) -> None:
        super().__init__(message, status_code, code=ErrorCode.FILE_SCAN_FAILED)


class QuotaExceeded(RapidlyError):
    """The caller has exceeded their storage or request quota."""

    def __init__(
        self,
        message: str = "Quota exceeded",
        status_code: int = _STATUS_TOO_MANY_REQUESTS,
    ) -> None:
        super().__init__(message, status_code, code=ErrorCode.QUOTA_EXCEEDED)


class ShareExpired(RapidlyError):
    """The shared link or resource has expired."""

    def __init__(
        self, message: str = "Share expired", status_code: int = _STATUS_GONE
    ) -> None:
        super().__init__(message, status_code, code=ErrorCode.SHARE_EXPIRED)


# ── Server errors ─────────────────────────────────────────────────────


class InternalServerError(RapidlyError):
    def __init__(
        self,
        message: str = "Internal Server Error",
        status_code: int = _STATUS_INTERNAL,
    ) -> None:
        super().__init__(message, status_code, code=ErrorCode.INTERNAL_ERROR)


# ── Validation errors ─────────────────────────────────────────────────


class ValidationError(TypedDict):
    """Structure for a hand-built validation error entry."""

    loc: tuple[int | str, ...]
    msg: LiteralString
    type: LiteralString
    input: Any
    ctx: NotRequired[dict[str, Any]]
    url: NotRequired[str]


def validation_error(
    field: str,
    msg: str,
    input: Any,
    *,
    loc_prefix: str = "body",
) -> ValidationError:
    """Build a single validation-error dict for use with ``RequestValidationError``."""
    return ValidationError(
        type="value_error", loc=(loc_prefix, field), msg=msg, input=input
    )


class RequestValidationError(RapidlyError):
    """Converts hand-built validation errors into the same format Pydantic produces."""

    def __init__(self, errors: Sequence[ValidationError]) -> None:
        self._errors = errors

    def errors(self) -> list[ErrorDetails]:
        init_errors: list[InitErrorDetails] = [
            {
                "type": PydanticCustomError(e["type"], e["msg"]),
                "loc": e["loc"],
                "input": e["input"],
            }
            for e in self._errors
        ]
        return PydanticValidationError.from_exception_data(
            type(self).__name__, init_errors
        ).errors()


__all__ = [
    "BackgroundTaskError",
    "BadRequest",
    "ErrorCode",
    "FileScanFailed",
    "InternalServerError",
    "NotPermitted",
    "PaymentNotReady",
    "QuotaExceeded",
    "RapidlyError",
    "RedirectionError",
    "RequestValidationError",
    "ResourceAlreadyExists",
    "ResourceNotFound",
    "ShareExpired",
    "Unauthorized",
    "ValidationError",
    "validation_error",
]
