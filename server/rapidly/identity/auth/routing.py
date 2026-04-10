"""Route-level auth documentation for OpenAPI.

Inspects endpoint type-hints for ``_Authenticator`` dependencies and
enriches the generated OpenAPI spec with ``x-rapidly-allowed-subjects``
and required-scope annotations.
"""

import inspect
import typing
from collections.abc import Callable

from fastapi.params import Depends
from fastapi.routing import APIRoute

from rapidly.identity.auth.dependencies import _Authenticator
from rapidly.identity.auth.scope import RESERVED_SCOPES, Scope


def _find_authenticator(endpoint: Callable[..., typing.Any]) -> _Authenticator | None:
    """Return the first ``_Authenticator`` dependency on *endpoint*, if any."""
    for param_type in typing.get_type_hints(endpoint, include_extras=True).values():
        if typing.get_origin(param_type) is not typing.Annotated:
            continue
        meta = param_type.__metadata__
        if not meta or not isinstance(meta[0], Depends):
            continue
        dep = meta[0].dependency
        if isinstance(dep, _Authenticator):
            return dep
    return None


def _build_scopes_section(required_scopes: set[Scope] | None) -> str:
    """Return a Markdown snippet listing the non-reserved scopes."""
    visible = sorted(s for s in (required_scopes or ()) if s not in RESERVED_SCOPES)
    if not visible:
        return ""
    formatted = " ".join(f"`{s}`" for s in visible)
    return f"\n\n**Scopes**: {formatted}"


class AuthDocumentedRoute(APIRoute):
    """
    A subclass of ``APIRoute`` that automatically documents the
    allowed subjects and scopes for every authenticated endpoint.
    """

    def __init__(
        self, path: str, endpoint: Callable[..., typing.Any], **kwargs: typing.Any
    ) -> None:
        openapi_extra = kwargs.get("openapi_extra") or {}

        if "x-rapidly-allowed-subjects" not in openapi_extra:
            authenticator = _find_authenticator(endpoint)
            if authenticator is not None:
                subject_names = sorted(
                    s.__name__ for s in authenticator.allowed_subjects
                )
                kwargs["openapi_extra"] = {
                    "x-rapidly-allowed-subjects": subject_names,
                    **openapi_extra,
                }
                base_description = kwargs["description"] or inspect.cleandoc(
                    endpoint.__doc__ or ""
                )
                kwargs["description"] = base_description + _build_scopes_section(
                    authenticator.required_scopes
                )

        super().__init__(path, endpoint, **kwargs)


__all__ = ["AuthDocumentedRoute"]
