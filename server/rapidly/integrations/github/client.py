"""GitHub API client factory using ``githubkit``.

Constructs authenticated GitHub clients for user-token authentication
and provides a response-status helper.
"""

from typing import Any

from githubkit import (
    GitHub,
    Response,
    TokenAuthStrategy,
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnexpectedStatusCode(Exception): ...


class AuthenticationRequired(UnexpectedStatusCode): ...


class Forbidden(UnexpectedStatusCode): ...


class NotFound(UnexpectedStatusCode): ...


class ValidationFailed(UnexpectedStatusCode): ...


_STATUS_EXCEPTIONS = {
    401: AuthenticationRequired,
    403: Forbidden,
    404: NotFound,
    422: ValidationFailed,
}


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


def ensure_expected_response(
    response: Response[Any], accepted: set[int] = {200, 304}
) -> bool:
    code = response.status_code
    if code in accepted:
        return True

    exc_class = _STATUS_EXCEPTIONS.get(code, UnexpectedStatusCode)
    raise exc_class()


# ---------------------------------------------------------------------------
# Client constructors
# ---------------------------------------------------------------------------


def get_client(access_token: str) -> GitHub[TokenAuthStrategy]:
    return GitHub(access_token, http_cache=False)


__all__ = [
    "GitHub",
    "Response",
    "TokenAuthStrategy",
    "get_client",
]
