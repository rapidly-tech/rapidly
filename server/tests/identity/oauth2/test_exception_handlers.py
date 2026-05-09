"""Tests for ``rapidly/identity/oauth2/exception_handlers.py``.

The handler serialises ``OAuth2Error`` into an HTTP response. Every
client that handles OAuth2 errors keys on the status code + JSON body
shape; silent drift here breaks error handling across every registered
integration.
"""

from __future__ import annotations

import json

import pytest
from authlib.oauth2 import OAuth2Error

from rapidly.identity.oauth2.exception_handlers import (
    _serialise_body,
    oauth2_error_exception_handler,
)


class TestSerialiseBody:
    def test_serialises_a_dict_to_json_string(self) -> None:
        out = _serialise_body({"error": "invalid_request"})
        assert json.loads(out) == {"error": "invalid_request"}

    def test_decodes_utf8_bytes_to_string(self) -> None:
        assert _serialise_body(b'{"error":"x"}') == '{"error":"x"}'

    def test_passes_through_a_string(self) -> None:
        assert _serialise_body('{"error":"x"}') == '{"error":"x"}'

    def test_preserves_non_ascii_characters_in_bytes_input(self) -> None:
        # UTF-8 decoding — non-ASCII must survive the round-trip.
        assert _serialise_body("café".encode()) == "café"


@pytest.mark.asyncio
class TestOauth2ErrorExceptionHandler:
    async def test_returns_response_with_the_error_status_code(self) -> None:
        # ``OAuth2Error`` advertises ``status_code`` (default 400) —
        # the handler must propagate it.
        exc = OAuth2Error(description="nope")
        resp = await oauth2_error_exception_handler(None, exc)  # type: ignore[arg-type]
        assert resp.status_code == exc.status_code

    async def test_body_is_json_encoded_error_payload(self) -> None:
        exc = OAuth2Error(description="invalid token")
        resp = await oauth2_error_exception_handler(None, exc)  # type: ignore[arg-type]
        # Parse the body and assert it's a valid JSON object with the
        # ``error`` key OAuth2 clients expect.
        payload = json.loads(resp.body)
        assert "error" in payload

    async def test_content_type_header_is_application_json(self) -> None:
        exc = OAuth2Error()
        resp = await oauth2_error_exception_handler(None, exc)  # type: ignore[arg-type]
        assert resp.headers["content-type"] == "application/json"

    async def test_does_not_override_existing_content_type_from_exc(
        self,
    ) -> None:
        # ``setdefault`` — if the OAuth2Error pre-populated a Content-
        # Type via its ``get_headers``, the handler must NOT clobber
        # it. Subclass to force a custom header.
        class _ExplicitCt(OAuth2Error):
            def get_headers(self) -> list[tuple[str, str]]:
                return [("content-type", "application/problem+json")]

        exc = _ExplicitCt()
        resp = await oauth2_error_exception_handler(None, exc)  # type: ignore[arg-type]
        assert resp.headers["content-type"] == "application/problem+json"

    async def test_handles_an_error_with_a_description(self) -> None:
        exc = OAuth2Error(description="the provided token has expired")
        resp = await oauth2_error_exception_handler(None, exc)  # type: ignore[arg-type]
        payload = json.loads(resp.body)
        # ``error_description`` is the OAuth2 standard field name.
        assert payload.get("error_description") == "the provided token has expired"
