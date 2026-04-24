"""Tests for ``rapidly/identity/oauth2/requests.py``.

Starlette-to-Authlib bridge. Authlib's grant handlers operate on
``OAuth2Request`` / ``JsonRequest`` objects; these adapters wrap a
Starlette ``Request`` so pre-parsed form data, query parameters, and
JSON bodies reach the handlers in the shape Authlib expects.

Pins:
- ``_collect_form_values`` merges query + pre-parsed form into
  flat (single-value) + multi-value dicts; UploadFile values are
  filtered out (multipart file uploads don't belong in OAuth2 params)
- ``StarletteOAuth2Payload.data`` is the flat dict; ``.datalist`` is
  the multi — Authlib grant handlers rely on both shapes
- ``StarletteOAuth2Request`` pulls ``user`` from ``request.state.user``
  with a None fallback (pre-auth requests have no user yet)
- ``StarletteJsonPayload.data`` reads from ``request.state.parsed_data``
  with a `{}` fallback — prevents None crashes in Authlib when the
  request-reading middleware hasn't run yet
- ``_PathParamsMixin.path_params`` exposes Starlette's path params so
  Authlib handlers can read route template values
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

from starlette.datastructures import ImmutableMultiDict

from rapidly.identity.oauth2.requests import (
    StarletteJsonPayload,
    StarletteJsonRequest,
    StarletteOAuth2Payload,
    StarletteOAuth2Request,
    _collect_form_values,
)


def _make_request(
    *,
    method: str = "POST",
    query: dict[str, str] | list[tuple[str, str]] | None = None,
    form: dict[str, Any] | list[tuple[str, Any]] | None = None,
    path_params: dict[str, Any] | None = None,
    state_user: Any = None,
    state_parsed_data: dict[str, Any] | None = None,
    url_for: Callable[..., Any] | None = None,
) -> Any:
    """Build a MagicMock Request — spec-shape to avoid attribute accidents."""
    req = MagicMock()
    req.method = method
    req.url = "https://api.example.test/oauth2/token"
    req.headers = {}
    req.query_params = ImmutableMultiDict(
        list(query.items() if isinstance(query, dict) else (query or []))
    )
    # ``_form`` is None when no form was pre-parsed.
    if form is None:
        req._form = None
    else:
        req._form = ImmutableMultiDict(
            list(form.items() if isinstance(form, dict) else form)
        )
    req.path_params = path_params or {}
    req.state = MagicMock()
    req.state.user = state_user
    # ``getattr(..., "parsed_data", None)`` — leaving parsed_data
    # unset forces the None fallback, setting it tests the populated
    # path.
    if state_parsed_data is None:
        # Remove the attribute so getattr returns the None fallback.
        del req.state.parsed_data
    else:
        req.state.parsed_data = state_parsed_data
    if url_for is not None:
        req.url_for = url_for
    return req


class TestCollectFormValues:
    def test_flat_and_multi_from_query_only(self) -> None:
        req = _make_request(
            query={"grant_type": "authorization_code", "scope": "email"}
        )
        flat, multi = _collect_form_values(req)
        assert flat == {"grant_type": "authorization_code", "scope": "email"}
        assert multi == {
            "grant_type": ["authorization_code"],
            "scope": ["email"],
        }

    def test_merges_query_and_form(self) -> None:
        req = _make_request(
            query={"grant_type": "authorization_code"},
            form={"code": "abc", "redirect_uri": "https://c.test/cb"},
        )
        flat, multi = _collect_form_values(req)
        assert flat["grant_type"] == "authorization_code"
        assert flat["code"] == "abc"
        assert flat["redirect_uri"] == "https://c.test/cb"

    def test_multi_value_key_preserves_order(self) -> None:
        # OAuth2 ``scope=x+y`` submits as a single entry, but a
        # client submitting ``scope=a&scope=b`` ends up in multi
        # with order preserved — grant handlers iterate the list.
        req = _make_request(query=[("scope", "a"), ("scope", "b")])
        flat, multi = _collect_form_values(req)
        assert multi["scope"] == ["a", "b"]
        # ``flat`` keeps the first entry (Authlib's documented
        # contract — only single-value params are used here).
        assert flat["scope"] == "a"

    def test_upload_files_are_filtered_out(self) -> None:
        # OAuth2 endpoints never accept multipart file uploads. A
        # regression that let UploadFile objects flow through would
        # crash Authlib's dict processing.
        from starlette.datastructures import UploadFile

        upload = MagicMock(spec=UploadFile)
        req = _make_request(form=[("code", "x"), ("file", upload), ("scope", "email")])
        flat, multi = _collect_form_values(req)
        assert "file" not in flat
        assert "file" not in multi
        assert flat == {"code": "x", "scope": "email"}


class TestStarletteOAuth2Payload:
    def test_data_and_datalist_exposed(self) -> None:
        req = _make_request(query=[("grant_type", "refresh_token"), ("scope", "a")])
        payload = StarletteOAuth2Payload(req)
        assert payload.data == {"grant_type": "refresh_token", "scope": "a"}
        assert payload.datalist == {
            "grant_type": ["refresh_token"],
            "scope": ["a"],
        }


class TestStarletteOAuth2Request:
    def test_args_pulled_from_query(self) -> None:
        req = _make_request(query={"state": "nonce"})
        w = StarletteOAuth2Request(req)
        assert w.args == {"state": "nonce"}

    def test_form_pulled_from_preparsed_form(self) -> None:
        req = _make_request(form={"code": "abc"})
        w = StarletteOAuth2Request(req)
        assert w.form == {"code": "abc"}

    def test_form_is_empty_when_not_preparsed(self) -> None:
        req = _make_request(form=None)
        w = StarletteOAuth2Request(req)
        assert w.form == {}

    def test_user_pulled_from_request_state(self) -> None:
        sentinel = object()
        req = _make_request(state_user=sentinel)
        w = StarletteOAuth2Request(req)
        assert w.user is sentinel

    def test_user_defaults_to_none_when_missing(self) -> None:
        # Pre-auth OAuth2 requests (anonymous authorize, token
        # exchange) don't have request.state.user. The adapter
        # must NOT crash — Authlib's grant handlers expect
        # user=None in that case.
        req = _make_request()
        req.state = MagicMock(spec=[])  # no attributes
        w = StarletteOAuth2Request(req)
        assert w.user is None


class TestPathParamsMixin:
    def test_exposes_starlette_path_params(self) -> None:
        # ``_PathParamsMixin.path_params`` reads ``self._request`` —
        # StarletteJsonRequest sets that attribute in its ctor so
        # the mixin can surface path params to Authlib handlers.
        req = _make_request(path_params={"client_id": "c"})
        w = StarletteJsonRequest(req)
        assert w.path_params == {"client_id": "c"}


class TestStarletteJsonPayload:
    def test_parsed_data_flows_to_data(self) -> None:
        req = _make_request(state_parsed_data={"client_name": "acme"})
        payload = StarletteJsonPayload(req)
        assert payload.data == {"client_name": "acme"}

    def test_missing_parsed_data_falls_back_to_empty(self) -> None:
        # Load-bearing defensive default: the request-reading
        # middleware populates state.parsed_data, but if it hasn't
        # run (e.g. for an endpoint that bypasses it), Authlib
        # must get ``{}`` not None — otherwise ``data.get(...)``
        # would crash.
        req = _make_request(state_parsed_data=None)
        payload = StarletteJsonPayload(req)
        assert payload.data == {}


class TestStarletteJsonRequest:
    def test_url_for_delegates_to_starlette(self) -> None:
        captured: dict[str, Any] = {}

        def fake_url_for(name: str, /, **kwargs: Any) -> str:
            captured["name"] = name
            captured["kwargs"] = kwargs
            return f"https://x/{name}"

        req = _make_request(url_for=fake_url_for)
        w = StarletteJsonRequest(req)
        result = w.url_for("oauth2:create_client", tenant="acme")
        assert str(result) == "https://x/oauth2:create_client"
        assert captured == {
            "name": "oauth2:create_client",
            "kwargs": {"tenant": "acme"},
        }
