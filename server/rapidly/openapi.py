"""OpenAPI schema factory and endpoint tag registry.

Builds the custom OpenAPI document by composing a pipeline of schema
transformers that inject metadata queries, OAuth2 form schemas, and
other vendor extensions into the generated specification.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from rapidly.config import Environment, settings

# ---------------------------------------------------------------------------
# Schema transformer type
# ---------------------------------------------------------------------------

type SchemaTransformer = Callable[[dict[str, Any]], dict[str, Any]]


def _load_transformers() -> tuple[SchemaTransformer, ...]:
    """Late-import schema transformers to avoid circular dependencies."""
    from rapidly.core.metadata import add_metadata_query_schema
    from rapidly.identity.oauth2.types import add_oauth2_form_schemas

    return (add_metadata_query_schema, add_oauth2_form_schemas)


# ---------------------------------------------------------------------------
# Tag registry
# ---------------------------------------------------------------------------


class APITag(StrEnum):
    """Controls which endpoints appear in different documentation views."""

    public = "public"
    private = "private"
    mcp = "mcp"

    @classmethod
    def metadata(cls) -> list[dict[str, Any]]:
        return [
            {
                "name": cls.public,
                "description": (
                    "Public Rapidly API -- documented and available to integrators."
                ),
            },
            {
                "name": cls.private,
                "description": ("Internal endpoints used by the Rapidly dashboard."),
            },
            {
                "name": cls.mcp,
                "description": "Endpoints exposed via the MCP server.",
            },
        ]


# ---------------------------------------------------------------------------
# Configuration dict consumed by ``FastAPI(...)``
# ---------------------------------------------------------------------------

_HIDE_DOCS = settings.is_environment({Environment.sandbox, Environment.production})

OPENAPI_PARAMETERS: dict[str, Any] = {
    "title": "Rapidly API",
    "summary": "Rapidly HTTP and Webhooks API",
    "version": "0.1.0",
    "description": "Rapidly file-sharing API",
    "docs_url": None if _HIDE_DOCS else "/docs",
    "redoc_url": None if _HIDE_DOCS else "/redoc",
    "openapi_tags": APITag.metadata(),
    "servers": [
        {
            "url": "https://api.rapidly.tech",
            "description": "Production",
        },
    ],
}


# ---------------------------------------------------------------------------
# Schema generation pipeline
# ---------------------------------------------------------------------------


def _build_base_schema(app: FastAPI) -> dict[str, Any]:
    """Extract the raw OpenAPI schema from the FastAPI app."""
    return get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        summary=app.summary,
        description=app.description,
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
        routes=app.routes,
        webhooks=app.webhooks.routes,
        tags=app.openapi_tags,
        servers=app.servers,
        separate_input_output_schemas=app.separate_input_output_schemas,
    )


def _apply_transformers(
    schema: dict[str, Any], transformers: tuple[SchemaTransformer, ...]
) -> dict[str, Any]:
    """Apply each transformer to the schema in sequence."""
    return functools.reduce(lambda s, fn: fn(s), transformers, schema)


def set_openapi_generator(app: FastAPI) -> None:
    """Replace the default OpenAPI generator with one that runs the
    Rapidly schema-transformer pipeline."""

    transformers = _load_transformers()

    def _generate() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = _build_base_schema(app)
        schema = _apply_transformers(schema, transformers)
        app.openapi_schema = schema
        return schema

    app.openapi = _generate  # type: ignore[method-assign]


__all__ = [
    "OPENAPI_PARAMETERS",
    "APITag",
    "set_openapi_generator",
]
