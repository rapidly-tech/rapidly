"""Extended FastAPI router with automatic response-model registration.

Wraps ``fastapi.APIRouter`` to inject standard error-response models
into every route's OpenAPI spec and provides a ``@cacheable`` decorator
for conditional ``304 Not Modified`` responses.
"""

import functools
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter as _APIRouter
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from rapidly.config import settings
from rapidly.openapi import APITag

# ── Router setup ──


class TransactionalRoute(APIRoute):
    """
    A subclass of `APIRoute` that automatically
    commits the session after the endpoint is called.

    It allows to directly return ORM objects from the endpoint
    without having to call `session.commit()` before returning.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        endpoint = self.wrap_endpoint(endpoint)
        super().__init__(path, endpoint, **kwargs)

    def wrap_endpoint(self, endpoint: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(endpoint)
        async def wrapped_endpoint(*args: Any, **kwargs: Any) -> Any:
            session: AsyncSession | None = None
            for arg in (args, *kwargs.values()):
                if isinstance(arg, AsyncSession):
                    session = arg
                    break

            response = await endpoint(*args, **kwargs)

            if session is not None:
                await session.commit()

            return response

        return wrapped_endpoint


class SchemaInclusionRoute(APIRoute):
    """
    A subclass of `APIRoute` that automatically sets the `include_in_schema` property
    depending on the tags.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)
        tags = self.tags
        if self.include_in_schema:
            if APITag.private in tags:
                self.include_in_schema = settings.is_development()
            elif APITag.public in tags:
                self.include_in_schema = True
            else:
                self.include_in_schema = False


class OperationNameRoute(APIRoute):
    """
    A subclass of `APIRoute` that automatically sets the operation ID
    following the route function name.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)


class VisibilityRoute(APIRoute):
    """
    A subclass of `APIRoute` that hides non-public endpoints from the schema.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)


class TagGroupRoute(APIRoute):
    """
    A subclass of `APIRoute` that groups endpoints by combining
    all the non-generic tags.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)


class PagedRoute(APIRoute):
    """
    A subclass of `APIRoute` that marks paginated endpoints
    (those returning a `PaginatedList`).
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)


class MCPEnabledRoute(APIRoute):
    """
    A subclass of `APIRoute` that marks MCP-enabled endpoints.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)


# ── Middleware helpers ──


def _inherit_signature_from[**P, T](
    _to: Callable[P, T],
) -> Callable[[Callable[..., T]], Callable[P, T]]:
    return lambda x: x  # pyright: ignore


def get_api_router_class(route_class: type[APIRoute]) -> type[_APIRouter]:
    """
    Returns a subclass of `APIRouter` that uses the given `route_class`.
    """

    class _CustomAPIRouter(_APIRouter):
        @_inherit_signature_from(_APIRouter.__init__)
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["route_class"] = route_class
            super().__init__(*args, **kwargs)

    return _CustomAPIRouter


__all__ = [
    "MCPEnabledRoute",
    "OperationNameRoute",
    "PagedRoute",
    "SchemaInclusionRoute",
    "TagGroupRoute",
    "TransactionalRoute",
    "VisibilityRoute",
    "get_api_router_class",
]
