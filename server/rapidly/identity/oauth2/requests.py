"""Starlette-to-Authlib request bridge.

Authlib's grant handlers operate on ``OAuth2Request`` and ``JsonRequest``
objects. These adapters wrap a Starlette ``Request`` so that parsed form
data, query parameters, and JSON bodies are surfaced through the interface
Authlib expects -- without pulling in any async I/O at construction time
(the caller must pre-parse the form before instantiation).
"""

import typing
from collections import defaultdict

from authlib.oauth2.rfc6749 import (
    JsonPayload,
    JsonRequest,
    OAuth2Payload,
    OAuth2Request,
)
from starlette.datastructures import URL, ImmutableMultiDict, UploadFile
from starlette.requests import Request

# ---------------------------------------------------------------------------
# Shared mixin -- exposes Starlette path params to Authlib handlers
# ---------------------------------------------------------------------------


class _PathParamsMixin:
    """Give Authlib request wrappers access to Starlette's path parameters."""

    _request: Request

    @property
    def path_params(self) -> dict[str, typing.Any]:
        return self._request.path_params


# ---------------------------------------------------------------------------
# Standard OAuth2 (form-encoded) request adapters
# ---------------------------------------------------------------------------


def _collect_form_values(
    request: Request,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Merge query params and pre-parsed form data into flat + multi-value dicts."""
    multi: dict[str, list[str]] = defaultdict(list)
    sources: list[ImmutableMultiDict[str, str | UploadFile]] = [request.query_params]
    if request._form is not None:
        sources.append(request._form)
    for src in sources:
        for key, val in src.multi_items():
            if not isinstance(val, UploadFile):
                multi[key].append(val)
    multi_dict = dict(multi)
    flat = {k: vals[0] for k, vals in multi_dict.items()}
    return flat, multi_dict


class StarletteOAuth2Payload(OAuth2Payload):
    def __init__(self, request: Request) -> None:
        flat, multi = _collect_form_values(request)
        self._data = flat
        self._datalist = multi

    @property
    def data(self) -> dict[str, str]:
        return self._data

    @property
    def datalist(self) -> dict[str, list[str]]:
        return self._datalist


class StarletteOAuth2Request(_PathParamsMixin, OAuth2Request):
    def __init__(self, request: Request):
        super().__init__(request.method, str(request.url), headers=request.headers)
        self.user = getattr(request.state, "user", None)
        self.payload = StarletteOAuth2Payload(request)
        self._args = dict(request.query_params)
        self._form = dict(request._form) if request._form else {}

    @property
    def args(self) -> dict[str, str | None]:
        return typing.cast(dict[str, str | None], self._args)

    @property
    def form(self) -> dict[str, str]:
        return typing.cast(dict[str, str], self._form)


# ---------------------------------------------------------------------------
# JSON request adapter (used by dynamic client registration endpoints)
# ---------------------------------------------------------------------------


class StarletteJsonPayload(JsonPayload):
    def __init__(self, request: Request) -> None:
        self._data = getattr(request.state, "parsed_data", None)

    @property
    def data(self) -> dict[str, str]:
        return self._data or {}


class StarletteJsonRequest(_PathParamsMixin, JsonRequest):
    credential: str | None = None

    def __init__(self, request: Request):
        super().__init__(request.method, str(request.url), request.headers)
        self.user = getattr(request.state, "user", None)
        self.payload = StarletteJsonPayload(request)
        self._request = request

    def url_for(self, name: str, /, **path_params: typing.Any) -> URL:
        return self._request.url_for(name, **path_params)
