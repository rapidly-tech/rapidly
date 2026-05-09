"""URL safety and manipulation helpers."""

from typing import Annotated
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import Depends, Query
from safe_redirect_url import url_has_allowed_host_and_scheme

from rapidly.config import settings


def get_safe_return_url(return_to: str | None) -> str:
    """Validate *return_to* against the allow-list, falling back to the default path."""
    default = settings.generate_frontend_url(settings.FRONTEND_DEFAULT_RETURN_PATH)

    if return_to is None:
        return default

    if not url_has_allowed_host_and_scheme(return_to, settings.ALLOWED_HOSTS):
        return default

    # Bare paths get the frontend origin prepended.
    parsed = urlparse(return_to)
    if not parsed.netloc:
        return settings.generate_frontend_url(return_to)

    return return_to


async def _resolve_return_to(return_to: str | None = Query(None)) -> str:
    return get_safe_return_url(return_to)


ReturnTo = Annotated[str, Depends(_resolve_return_to)]


def add_query_parameters(url: str, **params: str | list[str]) -> str:
    """Append or override query parameters on *url*."""
    scheme, netloc, path, path_params, query, fragment = urlparse(url)
    merged = {**parse_qs(query), **params}
    return urlunparse(
        (scheme, netloc, path, path_params, urlencode(merged, doseq=True), fragment)
    )
