"""User-defined key-value attributes for Rapidly resources.

The public API term is "attributes" (or "metadata" for backward compat).
Internally the JSONB column is called ``user_metadata`` for migration
stability.

This module provides:

- **ORM layer** -- ``MetadataMixin`` adds a JSONB column to any model
- **Pydantic layer** -- ``MetadataInputMixin`` / ``MetadataOutputMixin``
- **Query layer** -- ``MetadataQuery`` FastAPI dependency + filter builders
- **Nested access** -- dot-path traversal for both dicts and JSONB columns
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import Depends, Request
from pydantic import AliasChoices, BaseModel, Field, StringConstraints
from sqlalchemy import ColumnExpressionArgument, Select, and_, or_, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

# ---------------------------------------------------------------------------
# Column type
# ---------------------------------------------------------------------------

MetadataColumn = Annotated[
    dict[str, Any], mapped_column(JSONB, nullable=False, default=dict)
]


class MetadataMixin:
    """Adds a ``user_metadata`` JSONB column to a SQLAlchemy model."""

    user_metadata: Mapped[MetadataColumn]


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

MAXIMUM_KEYS: int = 50
_KEY_MIN, _KEY_MAX = 1, 40
_VAL_MIN, _VAL_MAX = 1, 500

MetadataKey = Annotated[
    str, StringConstraints(min_length=_KEY_MIN, max_length=_KEY_MAX)
]
_MetadataValueStr = Annotated[
    str, StringConstraints(min_length=_VAL_MIN, max_length=_VAL_MAX)
]
MetadataValue = _MetadataValueStr | int | float | bool

METADATA_DESCRIPTION = (
    "{heading}\n\n"
    f"Keys: string, max **{_KEY_MAX}** chars.  "
    f"Values: string (max **{_VAL_MAX}** chars), integer, float, or boolean.  "
    f"Limit: **{MAXIMUM_KEYS}** pairs."
)

MetadataField = Annotated[
    dict[MetadataKey, MetadataValue],
    Field(
        max_length=MAXIMUM_KEYS,
        description=METADATA_DESCRIPTION.format(heading="Custom key-value attributes."),
    ),
]


# ---------------------------------------------------------------------------
# Pydantic mixins
# ---------------------------------------------------------------------------


class MetadataInputMixin(BaseModel):
    """Accept ``metadata`` on create/update, persist as ``user_metadata``."""

    metadata: MetadataField = Field(
        default_factory=dict, serialization_alias="user_metadata"
    )


type MetadataOutputType = dict[str, str | int | float | bool]


class MetadataOutputMixin(BaseModel):
    """Emit ``metadata`` in responses from the ``user_metadata`` column."""

    metadata: MetadataOutputType = Field(
        validation_alias=AliasChoices("user_metadata", "metadata")
    )


# ---------------------------------------------------------------------------
# OpenAPI schema helpers
# ---------------------------------------------------------------------------

_QUERY_SCHEMA_DEFINITION: dict[str, Any] = {
    "anyOf": [
        {
            "type": "object",
            "additionalProperties": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"},
                    {"type": "boolean"},
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "array", "items": {"type": "integer"}},
                    {"type": "array", "items": {"type": "boolean"}},
                ]
            },
        },
        {"type": "null"},
    ],
    "title": "MetadataQuery",
}


def add_metadata_query_schema(openapi_schema: dict[str, Any]) -> dict[str, Any]:
    """Inject the ``MetadataQuery`` component into an OpenAPI spec."""
    openapi_schema["components"]["schemas"]["MetadataQuery"] = _QUERY_SCHEMA_DEFINITION
    return openapi_schema


def get_metadata_query_openapi_schema() -> dict[str, Any]:
    """OpenAPI parameter descriptor for ``?metadata[key]=value`` filtering."""
    return {
        "name": "metadata",
        "in": "query",
        "required": False,
        "style": "deepObject",
        "schema": {"$ref": "#/components/schemas/MetadataQuery"},
        "description": (
            "Filter by metadata key-value pairs using ``deepObject`` "
            "style, e.g. ``?metadata[key]=value``."
        ),
    }


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

_METADATA_PARAM_RE = re.compile(r"metadata\[([^\]]+)\]")


def _parse_metadata_query(request: Request) -> dict[str, list[str]] | None:
    """Extract ``metadata[key]=value`` pairs from the query string."""
    collected: dict[str, list[str]] = {}
    for param_name, param_value in request.query_params.multi_items():
        match = _METADATA_PARAM_RE.match(param_name)
        if match is not None:
            collected.setdefault(match.group(1), []).append(param_value)
    return collected


MetadataQuery = Annotated[dict[str, list[str]], Depends(_parse_metadata_query)]


# ---------------------------------------------------------------------------
# SQLAlchemy filtering
# ---------------------------------------------------------------------------


def get_metadata_clause[M: MetadataMixin](
    model: type[M], query: MetadataQuery
) -> ColumnExpressionArgument[bool]:
    """Build a WHERE clause matching all requested metadata key-value pairs.

    Multiple values for the same key are OR-ed; different keys are AND-ed.
    """
    if not query:
        return true()
    conditions: list[ColumnExpressionArgument[bool]] = [
        or_(*(model.user_metadata[key].as_string() == v for v in values))
        for key, values in query.items()
    ]
    return and_(*conditions)


def apply_metadata_clause[M: MetadataMixin](
    model: type[M], statement: Select[tuple[M]], query: MetadataQuery
) -> Select[tuple[M]]:
    """Apply metadata-based filtering to an existing SELECT."""
    return statement.where(get_metadata_clause(model, query))


# ---------------------------------------------------------------------------
# Dot-path traversal helpers
# ---------------------------------------------------------------------------


def get_nested_metadata_value(data: dict[str, Any], property_path: str) -> Any:
    """Walk a nested dict via dot-separated path, returning ``None`` on miss.

    Example::

        get_nested_metadata_value({"a": {"b": 42}}, "a.b")  # => 42
    """
    if not property_path:
        return None
    cursor: Any = data
    for segment in property_path.split("."):
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(segment)
        if cursor is None:
            return None
    return cursor


def get_nested_metadata_attr[M: MetadataMixin](
    model: type[M], property_path: str
) -> Any:
    """Build a SQLAlchemy JSONB path expression from a dot-separated path.

    Example::

        get_nested_metadata_attr(Event, "_llm.total_tokens")
        # => Event.user_metadata["_llm"]["total_tokens"]
    """
    parts = property_path.split(".")
    expr = model.user_metadata[parts[0]]
    for part in parts[1:]:
        expr = expr[part]
    return expr
