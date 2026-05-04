"""FastAPI exception handler that serialises OAuth2 errors into HTTP responses."""

import json
from typing import Any

from authlib.oauth2 import OAuth2Error
from fastapi import Request, Response

# Header value forced on every OAuth2 error response.
_ERROR_CONTENT_TYPE = "application/json"


def _serialise_body(raw_body: dict[str, Any] | str | bytes) -> str:
    """Ensure the response body is a JSON string."""
    if isinstance(raw_body, dict):
        return json.dumps(raw_body)
    if isinstance(raw_body, bytes):
        return raw_body.decode("utf-8")
    return raw_body


async def oauth2_error_exception_handler(
    request: Request, exc: OAuth2Error
) -> Response:
    """Convert an ``OAuth2Error`` raised inside a route into a proper HTTP response."""
    status_code, body, raw_headers = exc()
    serialised = _serialise_body(body)
    headers_dict = {k: v for k, v in raw_headers}
    headers_dict.setdefault("content-type", _ERROR_CONTENT_TYPE)
    return Response(serialised, status_code=status_code, headers=headers_dict)


__all__ = ["OAuth2Error", "oauth2_error_exception_handler"]
