"""Tests for ``rapidly/integrations/github/client.py``.

Thin wrapper around ``githubkit``. Two testable surfaces:

- ``ensure_expected_response`` maps GitHub HTTP codes to specific
  exception classes so callers can ``except NotFound`` / ``except
  AuthenticationRequired`` instead of matching on magic numbers
- ``get_client`` disables httpcache at the transport layer — pinning
  prevents a regression that re-enables caching (which masks rate-
  limit errors by returning stale successful responses)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from rapidly.integrations.github.client import (
    _STATUS_EXCEPTIONS,
    AuthenticationRequired,
    Forbidden,
    NotFound,
    UnexpectedStatusCode,
    ValidationFailed,
    ensure_expected_response,
    get_client,
)


def _response(status: int) -> Any:
    r = MagicMock()
    r.status_code = status
    return r


class TestExceptionHierarchy:
    def test_all_specific_errors_subclass_unexpected_status(self) -> None:
        # ``except UnexpectedStatusCode`` should catch every
        # status-specific variant — callers write generic handlers
        # and refine only when they need 404-specific behaviour.
        for cls in (AuthenticationRequired, Forbidden, NotFound, ValidationFailed):
            assert issubclass(cls, UnexpectedStatusCode)


class TestStatusExceptionMap:
    def test_map_covers_401_403_404_422(self) -> None:
        # Pin the exact mapping. Adding a 5xx without wiring the
        # exception (or dropping one) must be intentional — every
        # call site pattern-matches on these classes.
        assert _STATUS_EXCEPTIONS == {
            401: AuthenticationRequired,
            403: Forbidden,
            404: NotFound,
            422: ValidationFailed,
        }


class TestEnsureExpectedResponse:
    @pytest.mark.parametrize("ok", [200, 304])
    def test_accepted_defaults_allow_ok_and_not_modified(self, ok: int) -> None:
        # 200 (OK) + 304 (Not Modified) are the default accepts —
        # 304 matters because GitHub uses ETag conditionals.
        assert ensure_expected_response(_response(ok)) is True

    @pytest.mark.parametrize(
        ("status", "exc"),
        [
            (401, AuthenticationRequired),
            (403, Forbidden),
            (404, NotFound),
            (422, ValidationFailed),
        ],
    )
    def test_maps_status_to_specific_exception(
        self, status: int, exc: type[Exception]
    ) -> None:
        with pytest.raises(exc):
            ensure_expected_response(_response(status))

    def test_unknown_status_raises_generic_unexpected(self) -> None:
        # 5xx / 418 / whatever — callers can still catch via the
        # base class.
        with pytest.raises(UnexpectedStatusCode):
            ensure_expected_response(_response(500))

    def test_unknown_status_is_not_a_specific_subclass(self) -> None:
        # Pin that 500 raises the bare base class, not any of the
        # 4 specific subclasses (NotFound / Forbidden / etc).
        with pytest.raises(UnexpectedStatusCode) as exc_info:
            ensure_expected_response(_response(500))
        assert type(exc_info.value) is UnexpectedStatusCode
        assert not isinstance(exc_info.value, NotFound)
        assert not isinstance(exc_info.value, Forbidden)

    def test_custom_accepted_set_widens_allowed(self) -> None:
        # A caller that knows 201 is a valid response for their
        # specific GitHub endpoint can pass it in the accepted set.
        assert ensure_expected_response(_response(201), accepted={201}) is True

    def test_custom_accepted_set_narrows_allowed(self) -> None:
        # If the caller passes ``accepted={200}``, 304 is NOT
        # allowed — the default set is overridden, not merged.
        with pytest.raises(UnexpectedStatusCode):
            ensure_expected_response(_response(304), accepted={200})


class TestGetClient:
    def test_disables_http_cache(self) -> None:
        # ``http_cache=False`` is load-bearing: GitHub's rate-limit
        # enforcement relies on each request hitting the API.
        # A cached stale response would mask rate-limit exhaustion
        # and hide 403 replies. Pinning catches a regression that
        # flips the default back on.
        from rapidly.integrations.github import client as C

        captured: dict[str, Any] = {}

        class _FakeGitHub:
            def __init__(self, auth: str, **kwargs: Any) -> None:
                captured["auth"] = auth
                captured.update(kwargs)

        original = C.GitHub
        C.GitHub = _FakeGitHub  # type: ignore[misc,assignment]
        try:
            get_client("gh_token_123")
        finally:
            C.GitHub = original  # type: ignore[misc]
        assert captured["auth"] == "gh_token_123"
        assert captured["http_cache"] is False


class TestExports:
    def test_all_declared(self) -> None:
        from rapidly.integrations.github import client as C

        assert set(C.__all__) == {
            "GitHub",
            "Response",
            "TokenAuthStrategy",
            "get_client",
        }
