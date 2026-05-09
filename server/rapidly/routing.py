"""Composite API route class for the Rapidly REST API.

Assembles all route-level mixins into a single ``APIRoute`` and exposes
a pre-configured ``APIRouter`` that uses it by default.
"""

from rapidly.core.routing import (
    MCPEnabledRoute,
    OperationNameRoute,
    PagedRoute,
    SchemaInclusionRoute,
    TagGroupRoute,
    TransactionalRoute,
    VisibilityRoute,
    get_api_router_class,
)
from rapidly.identity.auth.routing import AuthDocumentedRoute


class APIRoute(
    TransactionalRoute,
    SchemaInclusionRoute,
    AuthDocumentedRoute,
    VisibilityRoute,
    OperationNameRoute,
    TagGroupRoute,
    MCPEnabledRoute,
    PagedRoute,
):
    """Unified route class combining all Rapidly API behaviours."""


APIRouter = get_api_router_class(APIRoute)

__all__ = ["APIRoute", "APIRouter"]
